"""B.5: ETL del corpus sintético; solo main puede solicitar embeddings."""

import argparse
import copy
import json
import math
import os
from pathlib import Path
import re
import tempfile
from types import SimpleNamespace

import httpx
import numpy as np
from dotenv import load_dotenv
from google import genai
from google.genai import errors

from pipeline_vectorial import (
    DIMENSION, ConfigurationError, CorpusError, EmbeddingError,
    embed_documents, normalized_embeddings,
)

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "base_conocimiento_etl_sucia.json"
CLEAN = ROOT / "base_conocimiento.json"
META_FIELDS = {"proyecto", "plataforma", "modulo", "activo", "defect_id",
               "estado_defecto", "tags_regionales"}


class CollisionError(CorpusError):
    pass


class PurgeError(ValueError):
    pass


class OutputError(OSError):
    pass


def resolve_path(path: str | Path) -> Path:
    location = Path(path)
    return (location if location.is_absolute() else ROOT / location).resolve()


def extract(path: str | Path) -> list[dict]:
    documents = json.loads(resolve_path(path).read_text(encoding="utf-8"))
    if not isinstance(documents, list):
        raise CorpusError("La raíz debe ser una lista.")
    return documents


def validate_document(doc: dict) -> None:
    if not isinstance(doc, dict) or set(doc) != {"id", "descripcion_semantica", "metadatos"}:
        raise CorpusError("Claves documentales inválidas.")
    if any(not isinstance(doc[field], str) or not doc[field].strip()
           for field in ("id", "descripcion_semantica")):
        raise CorpusError("ID o descripción inválidos.")
    meta = doc["metadatos"]
    if not isinstance(meta, dict) or set(meta) != META_FIELDS:
        raise CorpusError("Claves de metadatos inválidas.")
    if type(meta["activo"]) is not bool:
        raise CorpusError("activo debe ser booleano real.")
    for field in META_FIELDS - {"activo", "tags_regionales"}:
        if not isinstance(meta[field], str) or not meta[field].strip():
            raise CorpusError("Metadato escalar inválido.")
    if meta["plataforma"] not in ("web", "android", "ios", "desktop"):
        raise CorpusError("Plataforma inválida.")
    tags = meta["tags_regionales"]
    if (not isinstance(tags, list) or not tags
            or any(not isinstance(tag, str) or not tag.strip() or tag != tag.lower() for tag in tags)
            or len(set(tags)) != len(tags)):
        raise CorpusError("Tags inválidos.")


def normalize(documents: list[dict]) -> tuple[list[dict], list[dict]]:
    if not isinstance(documents, list):
        raise CorpusError("La raíz debe ser una lista.")
    result = copy.deepcopy(documents)
    corrections = []
    for position, doc in enumerate(result):
        if not isinstance(doc, dict) or not isinstance(doc.get("metadatos"), dict):
            raise CorpusError("Documento o metadatos inválidos.")
        meta = doc["metadatos"]
        if "platform" in meta:
            if "plataforma" in meta and meta["plataforma"] != meta["platform"]:
                raise CorpusError("platform y plataforma contradictorias.")
            meta["plataforma"] = meta.pop("platform")
            corrections.append({"posicion": position, "id": doc.get("id"),
                                "correccion": "platform -> plataforma"})
        if isinstance(meta.get("activo"), str):
            value = meta["activo"].lower()
            if value not in ("true", "false"):
                raise CorpusError("String booleano inválido.")
            meta["activo"] = value == "true"
            corrections.append({"posicion": position, "id": doc.get("id"),
                                "correccion": "activo: string -> bool"})
        validate_document(doc)
    return result, corrections


def resolve_collisions(documents: list[dict]) -> tuple[list[dict], list[dict]]:
    result = copy.deepcopy(documents)
    for doc in result:
        validate_document(doc)
    reserved = {doc["id"] for doc in result}
    seen = set()
    changes = []
    for doc in result:
        original = doc["id"]
        if original in seen:
            stem = "DOC-DUP-" + original[4:] if original.startswith("DOC-") else original + "-DUP"
            candidate = stem
            suffix = 2
            while candidate in reserved:
                candidate = f"{stem}-{suffix}"
                suffix += 1
                if suffix > len(result) + 2:
                    raise CollisionError("No se pudo resolver la colisión.")
            reserved.add(candidate)
            doc["id"] = candidate
            changes.append({"id_original": original, "id_nuevo": candidate,
                            "motivo": "ID repetido; se conserva la primera aparición"})
        seen.add(doc["id"])
    return result, changes


def normalize_vectors(embeddings, count: int) -> np.ndarray:
    try:
        with np.errstate(over="ignore", invalid="ignore"):
            matrix = np.asarray(embeddings, dtype=np.float32)
    except (TypeError, ValueError, OverflowError) as error:
        raise EmbeddingError("Vectores inválidos.") from error
    if matrix.shape != (count, DIMENSION):
        raise EmbeddingError("Cantidad o dimensión de vectores inválidas.")
    response = SimpleNamespace(embeddings=[SimpleNamespace(values=row) for row in matrix])
    return normalized_embeddings(response, count)


def validate_threshold(value: float) -> None:
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or not 0 <= value <= 2):
        raise PurgeError("Umbral de distancia inválido; debe estar entre 0 y 2.")


def detectar_duplicados(documentos: list[dict], embeddings,
                         umbral_distancia: float) -> tuple[list[dict], list[dict]]:
    """Purga por distancia directa al canónico; evita fusiones por cadenas.

    Cada eliminado satisface el umbral respecto del conservado registrado.
    El orden prioriza IDs regulares; el resto conserva el orden de entrada.
    """
    validate_threshold(umbral_distancia)
    for doc in documentos:
        validate_document(doc)
    if len({doc["id"] for doc in documentos}) != len(documentos):
        raise CollisionError("Resolver IDs repetidos antes de la purga.")
    vectors = normalize_vectors(embeddings, len(documentos))
    order = sorted(range(len(documentos)), key=lambda i: (
        not bool(re.fullmatch(r"DOC-00[1-9]|DOC-01[0-5]", documentos[i]["id"])), i,
    ))
    kept = []
    removed = []
    removed_positions = set()
    for position in order:
        doc = documentos[position]
        meta = doc["metadatos"]
        for canonical in kept:
            original = documentos[canonical]
            if any(meta[field] != original["metadatos"][field]
                   for field in ("proyecto", "plataforma", "modulo")):
                continue
            similarity = float(np.clip(np.dot(vectors[position], vectors[canonical]), -1.0, 1.0))
            distance = 1.0 - similarity
            if distance <= umbral_distancia:
                removed_positions.add(position)
                removed.append({
                    "id_conservado": original["id"], "id_eliminado": doc["id"],
                    "similitud_coseno": similarity, "distancia_coseno": distance,
                    "proyecto": meta["proyecto"], "plataforma": meta["plataforma"],
                    "modulo": meta["modulo"],
                    "motivo": "Distancia dentro del umbral y mismo proyecto/plataforma/módulo; prioridad canónica",
                })
                break
        else:
            kept.append(position)
    return [copy.deepcopy(doc) for i, doc in enumerate(documentos) if i not in removed_positions], removed


def validate_result(result: list[dict], clean: list[dict], removed: list[dict]) -> None:
    if len(removed) != 3 or len(result) != 15 or len(clean) != 15:
        raise PurgeError("Se esperaban tres eliminaciones y 15 documentos finales.")
    for documents in (result, clean):
        for doc in documents:
            validate_document(doc)
        if len({doc["id"] for doc in documents}) != len(documents):
            raise PurgeError("IDs finales repetidos.")
    if {doc["id"]: doc for doc in result} != {doc["id"]: doc for doc in clean}:
        raise PurgeError("El resultado no coincide íntegramente con la fuente limpia.")


def write_output(path: str | Path, result: list[dict]) -> None:
    destination = resolve_path(path)
    # Nunca sobrescribir fuentes, código, configuración o persistencias.
    if (destination in (INPUT.resolve(), CLEAN.resolve())
            or any(part in ("chroma_db", "faiss_index", ".git", ".venv") for part in destination.parts)
            or destination.suffix.lower() != ".json" or destination.exists()):
        raise OutputError("La salida debe ser un JSON nuevo fuera de las rutas protegidas.")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=destination.parent,
                                         delete=False) as file:
            temporary = Path(file.name)
            json.dump(result, file, ensure_ascii=False, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, destination)
    except (OSError, UnicodeError) as error:
        raise OutputError("No se pudo escribir la salida.") from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def load_configuration() -> tuple[str, str]:
    load_dotenv(ROOT / ".env")
    key = os.getenv("GEMINI_API_KEY", "").strip()
    model = os.getenv("GEMINI_EMBEDDING_MODEL", "").strip()
    if not key or not model:
        raise ConfigurationError("Falta configuración de embeddings.")
    return key, model


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--threshold", type=float, default=0.15)
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    try:
        validate_threshold(args.threshold)
        documents = extract(INPUT)
        if len(documents) != 18:
            raise CorpusError("Se esperaban 18 registros iniciales.")
        normalized, corrections = normalize(documents)
        normalized, collisions = resolve_collisions(normalized)
        if len(corrections) != 2 or len(collisions) != 1:
            raise CorpusError("Se esperaban dos correcciones y una colisión.")
        clean = extract(CLEAN)
        key, model = load_configuration()
        with genai.Client(api_key=key) as client:
            vectors = embed_documents(normalized, client, model)
        result, removed = detectar_duplicados(normalized, vectors, args.threshold)
        print("Datos académicos sintéticos; no son tickets externos.")
        print(f"Documentos extraídos: {len(documents)}")
        print(f"Correcciones estructurales: {len(corrections)}")
        for correction in corrections:
            print(json.dumps(correction, ensure_ascii=False))
        print(f"Colisiones resueltas: {len(collisions)}")
        for collision in collisions:
            print(json.dumps(collision, ensure_ascii=False))
        print(f"Modelo: {model.replace(key, '[REDACTADO]')}; dimensión: {DIMENSION}")
        print(f"Umbral preliminar: distancia <= {args.threshold}; similitud >= {1.0 - args.threshold}")
        for deletion in removed:
            print(json.dumps(deletion, ensure_ascii=False))
        print(f"Documentos finales: {len(result)}")
        validate_result(result, clean, removed)
        if args.output:
            write_output(args.output, result)
        print("El ETL reconstruyó la fuente limpia: coincidencia completa con base_conocimiento.json.")
        code = 0
    except ConfigurationError:
        print("Error: configuración ausente.")
        code = 2
    except json.JSONDecodeError:
        print("Error: JSON inválido.")
        code = 4
    except CollisionError:
        print("Error: colisión de IDs sin resolver.")
        code = 10
    except CorpusError:
        print("Error: estructura o cantidades iniciales inválidas.")
        code = 5
    except EmbeddingError:
        print("Error: embeddings inválidos.")
        code = 9
    except (httpx.NetworkError, httpx.TimeoutException):
        print("Error: red o timeout con Gemini.")
        code = 6
    except errors.APIError:
        print("Error: Gemini rechazó los embeddings.")
        code = 7
    except OutputError:
        print("Error: escritura de salida rechazada o fallida.")
        code = 8
    except PurgeError:
        print("Error: umbral o resultado inesperado de la purga; no se escribió salida.")
        code = 11
    except (OSError, UnicodeError):
        print("Error: archivo ilegible o codificación inválida.")
        code = 3
    print(f"Código de salida: {code}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
