"""A.4: FAISS persistente; búsqueda pura sobre un corpus sintético.

--load-only valida la persistencia sin crear clientes ni generar embeddings.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

import faiss
import httpx
import numpy as np
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

ROOT = Path(__file__).resolve().parent
DIMENSION = 768
FORMAT_VERSION = 1
# Códigos de salida para errores esperables, sin detalles remotos ni secretos.
EXIT_OK = 0
EXIT_CONFIGURATION = 2
EXIT_FILE = 3
EXIT_JSON = 4
EXIT_CORPUS = 5
EXIT_NETWORK = 6
EXIT_API = 7
EXIT_STORAGE = 8
EXIT_EMBEDDINGS = 9


class ConfigurationError(ValueError):
    pass


class CorpusError(ValueError):
    pass


class EmbeddingError(ValueError):
    pass


class StorageError(RuntimeError):
    pass


def load_configuration(load_only: bool = False) -> tuple[str, str, Path]:
    load_dotenv(ROOT / ".env")
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model = os.getenv("GEMINI_EMBEDDING_MODEL", "").strip()
    path = os.getenv("FAISS_INDEX_PATH", "").strip()
    # La recarga local no necesita credenciales, pero sí modelo y ruta.
    if not model or not path or (not load_only and not api_key):
        raise ConfigurationError("Falta configuración requerida para este modo.")
    index_path = Path(path)
    if not index_path.is_absolute():
        index_path = ROOT / index_path
    return api_key, model, index_path.resolve()


def load_corpus(path: Path) -> tuple[list[dict], str]:
    raw = path.read_bytes()
    documents = json.loads(raw.decode("utf-8"))
    if not isinstance(documents, list) or len(documents) != 15:
        raise CorpusError("El corpus debe contener exactamente 15 documentos.")
    ids = set()
    for doc in documents:
        if not isinstance(doc, dict):
            raise CorpusError("Documento inválido.")
        doc_id = doc.get("id")
        description = doc.get("descripcion_semantica")
        metadata = doc.get("metadatos")
        if not isinstance(doc_id, str) or not doc_id.strip() or doc_id in ids:
            raise CorpusError("IDs vacíos o duplicados.")
        if not isinstance(description, str) or not description.strip():
            raise CorpusError("Descripción vacía.")
        if not isinstance(metadata, dict):
            raise CorpusError("Metadatos inválidos.")
        ids.add(doc_id)
    return documents, hashlib.sha256(raw).hexdigest()


def normalized_embeddings(response: types.EmbedContentResponse, count: int) -> np.ndarray:
    embeddings = response.embeddings
    if embeddings is None or len(embeddings) != count:
        raise EmbeddingError("Cantidad incorrecta de embeddings.")
    if any(item.values is None or len(item.values) != DIMENSION for item in embeddings):
        raise EmbeddingError("Dimensión incorrecta de embeddings.")
    try:
        with np.errstate(over="ignore", invalid="ignore"):
            matrix = np.array([item.values for item in embeddings], dtype=np.float32)
    except (ValueError, TypeError, OverflowError) as error:
        raise EmbeddingError("Valores de embeddings inválidos.") from error
    if matrix.shape != (count, DIMENSION) or not np.isfinite(matrix).all():
        raise EmbeddingError("Embeddings no finitos o de forma inválida.")
    norms = np.linalg.norm(matrix.astype(np.float64), axis=1)
    if np.any(norms == 0):
        raise EmbeddingError("No se admiten vectores cero.")
    faiss.normalize_L2(matrix)
    if not np.isfinite(matrix).all() or not np.allclose(np.linalg.norm(matrix, axis=1), 1.0):
        raise EmbeddingError("No se pudo normalizar los embeddings.")
    return matrix


def embed_documents(documents: list[dict], client: genai.Client, model: str) -> np.ndarray:
    response = client.models.embed_content(
        model=model,
        contents=[doc["descripcion_semantica"] for doc in documents],
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_DOCUMENT", output_dimensionality=DIMENSION,
        ),
    )
    return normalized_embeddings(response, len(documents))


def embed_query(query: str, client: genai.Client, model: str) -> np.ndarray:
    response = client.models.embed_content(
        model=model, contents=query,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY", output_dimensionality=DIMENSION,
        ),
    )
    return normalized_embeddings(response, 1)


def expected_manifest(documents: list[dict], model: str, corpus_hash: str) -> dict:
    return {
        "format_version": FORMAT_VERSION, "embedding_model": model,
        "dimension": DIMENSION, "index_type": "IndexFlatIP",
        "metric": "cosine_via_normalized_inner_product",
        "ids": [doc["id"] for doc in documents],
        "document_count": len(documents), "corpus_sha256": corpus_hash,
    }


def manifest_path(index_path: Path) -> Path:
    return index_path.with_suffix(".meta.json")


def load_index(index_path: Path, expected: dict) -> faiss.Index:
    try:
        manifest = json.loads(manifest_path(index_path).read_text(encoding="utf-8"))
        index = faiss.read_index(str(index_path))
    except (OSError, UnicodeError, json.JSONDecodeError, RuntimeError) as error:
        raise StorageError("Índice o manifiesto ausente o ilegible; primero hay que construirlo.") from error
    if manifest != expected:
        raise StorageError("El manifiesto no coincide con el corpus o la configuración.")
    if (not isinstance(index, faiss.IndexFlatIP) or index.d != DIMENSION
            or index.ntotal != expected["document_count"]
            or index.metric_type != faiss.METRIC_INNER_PRODUCT):
        raise StorageError("Tipo, dimensión, cantidad o métrica del índice inválidos.")
    vectors = index.reconstruct_n(0, index.ntotal)
    if not np.isfinite(vectors).all() or not np.allclose(np.linalg.norm(vectors, axis=1), 1.0):
        raise StorageError("El índice contiene vectores inválidos o sin normalizar.")
    return index


def save_index(index: faiss.Index, index_path: Path, manifest: dict) -> None:
    temporary_paths = []
    try:
        index_path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(2):
            with tempfile.NamedTemporaryFile(dir=index_path.parent, delete=False) as file:
                temporary_paths.append(Path(file.name))
        faiss.write_index(index, str(temporary_paths[0]))
        temporary_paths[1].write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
        )
        # Cada reemplazo es atómico; una interrupción entre ambos se valida al recargar.
        os.replace(temporary_paths[0], index_path)
        os.replace(temporary_paths[1], manifest_path(index_path))
    except (OSError, RuntimeError) as error:
        raise StorageError("No se pudo persistir el índice y su manifiesto.") from error
    finally:
        for path in temporary_paths:
            path.unlink(missing_ok=True)


def get_or_build_index(index_path: Path, documents: list[dict], client: genai.Client,
                       model: str, corpus_hash: str) -> faiss.Index:
    expected = expected_manifest(documents, model, corpus_hash)
    if index_path.exists() or manifest_path(index_path).exists():
        try:
            index = load_index(index_path, expected)
        except StorageError as error:
            print(f"Regeneración controlada: {error}")
        else:
            print("Índice FAISS recargado desde disco. Embeddings documentales generados: 0.")
            return index
    vectors = embed_documents(documents, client, model)
    index = faiss.IndexFlatIP(DIMENSION)
    index.add(vectors)
    save_index(index, index_path, expected)
    print("Índice FAISS construido y persistido. Embeddings documentales generados: 15.")
    return index


def buscar_similares(consulta: str, client: genai.Client, model: str, index: faiss.Index,
                      documentos: list[dict], top_k: int = 3) -> list[dict]:
    if not isinstance(consulta, str) or not consulta.strip():
        raise CorpusError("La consulta no puede estar vacía.")
    if type(top_k) is not int or top_k <= 0:
        raise CorpusError("top_k debe ser un entero positivo.")
    if index.ntotal != len(documentos) or index.d != DIMENSION:
        raise StorageError("El índice no corresponde a los documentos.")
    query_vector = embed_query(consulta.strip(), client, model)
    scores, positions = index.search(query_vector, min(top_k, len(documentos)))
    results = []
    for score, position in zip(scores[0], positions[0]):
        if not 0 <= position < len(documentos):
            raise StorageError("Posición FAISS fuera del corpus.")
        doc = documentos[int(position)]
        meta = doc["metadatos"]
        similarity = float(np.clip(score, -1.0, 1.0))
        results.append({
            "posicion": int(position), "id": doc["id"],
            "defect_id": meta.get("defect_id"), "proyecto": meta.get("proyecto"),
            "plataforma": meta.get("plataforma"), "modulo": meta.get("modulo"),
            "activo": meta.get("activo"), "similitud_coseno": similarity,
            "distancia_coseno": 1.0 - similarity,
            "descripcion_semantica": doc["descripcion_semantica"],
        })
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--load-only", action="store_true")
    args = parser.parse_args(argv)
    api_key = ""
    try:
        api_key, model, path = load_configuration(args.load_only)
        documents, corpus_hash = load_corpus(ROOT / "base_conocimiento.json")
        if args.load_only:
            index = load_index(path, expected_manifest(documents, model, corpus_hash))
            safe_model = model.replace(api_key, "[REDACTADO]") if api_key else model
            print(f"Dimensión: {index.d}; ntotal: {index.ntotal}; modelo: {safe_model}")
            print("SHA-256 del corpus coincidente.")
            print("Recarga local verificada sin llamadas a la API.")
            return EXIT_OK
        queries = [
            "La app se cierra al abrir la cesta después de agregar un artículo agotado.",
            "El login devuelve 401 después de renovar una sesión vencida.",
            "El botón guardar sigue bloqueado después de corregir un campo inválido.",
        ]
        with genai.Client(api_key=api_key) as client:
            index = get_or_build_index(path, documents, client, model, corpus_hash)
            print("Resultados del corpus sintético; no confirman tickets externos.")
            for query in queries:
                print(f"\nConsulta: {query}")
                for rank, result in enumerate(buscar_similares(query, client, model, index, documents), 1):
                    active = str(result["activo"]).lower()
                    print(f"{rank}. {result['id']} / {result['defect_id']} | "
                          f"{result['proyecto']} | {result['plataforma']} | "
                          f"{result['modulo']} | activo={active}")
                    print(f"similitud_coseno={result['similitud_coseno']:.6f}; "
                          f"distancia_coseno={result['distancia_coseno']:.6f}")
                    print(result["descripcion_semantica"])
        return EXIT_OK
    except ConfigurationError:
        print("Error: configuración requerida ausente.")
        return EXIT_CONFIGURATION
    except json.JSONDecodeError:
        print("Error: JSON del corpus inválido.")
        return EXIT_JSON
    except CorpusError:
        print("Error: corpus, consulta o top_k inválidos.")
        return EXIT_CORPUS
    except EmbeddingError:
        print("Error: cantidad, dimensión o valores de embeddings inválidos.")
        return EXIT_EMBEDDINGS
    except (httpx.NetworkError, httpx.TimeoutException):
        print("Error: conexión o timeout con Gemini.")
        return EXIT_NETWORK
    except errors.APIError:
        print("Error: Gemini rechazó la solicitud de embeddings.")
        return EXIT_API
    except StorageError as error:
        print(f"Error de persistencia: {error}")
        return EXIT_STORAGE
    except (OSError, UnicodeError):
        print("Error: archivo inexistente, ilegible o con codificación inválida.")
        return EXIT_FILE
    except RuntimeError:
        print("Error: operación FAISS fallida.")
        return EXIT_STORAGE


if __name__ == "__main__":
    raise SystemExit(main())
