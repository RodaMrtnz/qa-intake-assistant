"""B.1: ingesta Chroma persistente; verify usa solo get/count, sin Gemini."""

import argparse
import json
import os
from pathlib import Path

import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
from chromadb.config import Settings
from chromadb.errors import ChromaError, NotFoundError
from chromadb.utils.embedding_functions import register_embedding_function
import httpx
import numpy as np
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

from pipeline_vectorial import (
    ConfigurationError, CorpusError, EmbeddingError, normalized_embeddings,
)

ROOT = Path(__file__).resolve().parent
DIMENSION = 768
COLLECTION_NAME = "qa_intake_knowledge"
SCHEMA_VERSION = 1
EXIT_OK = 0
EXIT_CONFIGURATION = 2
EXIT_FILE = 3
EXIT_JSON = 4
EXIT_CORPUS = 5
EXIT_NETWORK = 6
EXIT_API = 7
EXIT_CHROMA = 8
EXIT_EMBEDDINGS = 9
SCALAR_FIELDS = ("proyecto", "plataforma", "modulo", "activo", "defect_id", "estado_defecto")


class CollectionError(ValueError):
    pass


class HotEventError(CollectionError):
    pass


class RestorationError(CollectionError):
    pass


@register_embedding_function
class GeminiEmbeddingFunction(EmbeddingFunction[Documents]):
    """Cliente perezoso: get_config/build_from_config nunca crean clientes."""

    def __init__(self, model: str, api_key: str, dimension: int = DIMENSION,
                 client: genai.Client | None = None):
        if not isinstance(model, str) or not model.strip() or dimension != DIMENSION:
            raise ConfigurationError("Configuración de embeddings inválida.")
        self.model = model
        self.dimension = dimension
        self._api_key = api_key
        self._client = client

    @staticmethod
    def name() -> str:
        return "qa_intake_gemini"

    def get_config(self) -> dict:
        return {"model": self.model, "dimension": self.dimension}

    @staticmethod
    def build_from_config(config: dict) -> "GeminiEmbeddingFunction":
        GeminiEmbeddingFunction.validate_config(config)
        return GeminiEmbeddingFunction(
            model=config["model"], dimension=config["dimension"],
            api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        )

    @staticmethod
    def validate_config(config: dict) -> None:
        if (set(config) != {"model", "dimension"}
                or not isinstance(config["model"], str) or not config["model"].strip()
                or type(config["dimension"]) is not int or config["dimension"] != DIMENSION):
            raise ConfigurationError("Configuración persistida de embeddings inválida.")

    def default_space(self) -> str:
        return "cosine"

    def supported_spaces(self) -> list[str]:
        return ["cosine"]

    def _embed(self, texts: Documents, task: str) -> Embeddings:
        if not texts or any(not isinstance(text, str) or not text.strip() for text in texts):
            raise EmbeddingError("Textos de embeddings vacíos o inválidos.")
        config = types.EmbedContentConfig(task_type=task, output_dimensionality=self.dimension)
        if self._client is not None:
            response = self._client.models.embed_content(model=self.model, contents=texts, config=config)
        else:
            if not self._api_key:
                raise ConfigurationError("Falta GEMINI_API_KEY para generar embeddings.")
            with genai.Client(api_key=self._api_key) as client:
                response = client.models.embed_content(model=self.model, contents=texts, config=config)
        return normalized_embeddings(response, len(texts)).tolist()

    def __call__(self, input: Documents) -> Embeddings:
        return self._embed(input, "RETRIEVAL_DOCUMENT")

    def embed_query(self, input: Documents) -> Embeddings:
        return self._embed(input, "RETRIEVAL_QUERY")


def load_configuration(verify: bool = False) -> tuple[str, str, Path]:
    load_dotenv(ROOT / ".env")
    model = os.getenv("GEMINI_EMBEDDING_MODEL", "").strip()
    path = os.getenv("CHROMA_DB_PATH", "").strip()
    api_key = "" if verify else os.getenv("GEMINI_API_KEY", "").strip()
    if not model or not path or (not verify and not api_key):
        raise ConfigurationError("Falta configuración requerida.")
    location = Path(path)
    if not location.is_absolute():
        location = ROOT / location
    return api_key, model, location.resolve()


def corpus_records(documents: list[dict]) -> tuple[list[str], list[str], list[dict]]:
    if not isinstance(documents, list) or len(documents) != 15:
        raise CorpusError("Se requieren exactamente 15 documentos.")
    ids, texts, metadatas = [], [], []
    for doc in documents:
        if not isinstance(doc, dict) or set(doc) != {"id", "descripcion_semantica", "metadatos"}:
            raise CorpusError("Claves documentales inválidas.")
        doc_id, text, meta = doc["id"], doc["descripcion_semantica"], doc["metadatos"]
        if not isinstance(doc_id, str) or not doc_id.strip() or doc_id in ids:
            raise CorpusError("IDs vacíos o duplicados.")
        if not isinstance(text, str) or not text.strip():
            raise CorpusError("Descripción vacía.")
        if not isinstance(meta, dict) or set(meta) != set(SCALAR_FIELDS) | {"tags_regionales"}:
            raise CorpusError("Claves de metadatos inválidas.")
        if type(meta["activo"]) is not bool:
            raise CorpusError("activo debe ser booleano.")
        if any(not isinstance(meta[key], str) or not meta[key].strip()
               for key in SCALAR_FIELDS if key != "activo"):
            raise CorpusError("Metadatos escalares inválidos.")
        tags = meta["tags_regionales"]
        if not isinstance(tags, list) or not tags or any(not isinstance(tag, str) or not tag.strip() for tag in tags):
            raise CorpusError("Tags inválidos.")
        metadata = {key: meta[key] for key in SCALAR_FIELDS}
        metadata["tags_regionales_json"] = json.dumps(tags, ensure_ascii=False)
        ids.append(doc_id)
        texts.append(text)
        metadatas.append(metadata)
    return ids, texts, metadatas


def load_corpus() -> list[dict]:
    documents = json.loads((ROOT / "base_conocimiento.json").read_text(encoding="utf-8"))
    corpus_records(documents)
    return documents


def collection_metadata(model: str) -> dict:
    return {
        "hnsw:space": "cosine", "embedding_model": model,
        "embedding_dimension": DIMENSION, "corpus_document_count": 15,
        "schema_version": SCHEMA_VERSION,
    }


def persistent_client(path: Path):
    return chromadb.PersistentClient(path=str(path), settings=Settings(anonymized_telemetry=False))


def validate_collection(collection, model: str, ids: list[str]) -> None:
    metadata = collection.metadata or {}
    if any(metadata.get(key) != value for key, value in collection_metadata(model).items()):
        raise CollectionError("Colección incompatible; se necesita una migración explícita.")
    # configuration_json evita reconstruir la función remota durante get/count.
    config = collection.configuration_json
    if (config.get("hnsw") or {}).get("space") != "cosine":
        raise CollectionError("Métrica incompatible; se necesita una migración explícita.")
    ef = config.get("embedding_function") or {}
    if (ef.get("name") != GeminiEmbeddingFunction.name()
            or ef.get("config") != {"model": model, "dimension": DIMENSION}):
        raise CollectionError("Modelo o función incompatible; se necesita una migración explícita.")
    stored = collection.get(include=["embeddings"])
    if set(stored["ids"]) - set(ids):
        raise CollectionError("IDs adicionales; se necesita una migración explícita.")
    if stored["ids"]:
        matrix = np.asarray(stored["embeddings"])
        if matrix.shape != (len(stored["ids"]), DIMENSION) or not np.isfinite(matrix).all():
            raise CollectionError("Dimensión o vectores almacenados incompatibles; migración explícita requerida.")


def verify_collection(collection, documents: list[dict], model: str) -> None:
    ids, texts, metas = corpus_records(documents)
    validate_collection(collection, model, ids)
    stored = collection.get(include=["documents", "metadatas"])
    if collection.count() != 15 or len(stored["ids"]) != 15 or set(stored["ids"]) != set(ids):
        raise CollectionError("Cantidad o IDs no coinciden con el corpus.")
    expected = dict(zip(ids, zip(texts, metas)))
    for doc_id, text, meta in zip(stored["ids"], stored["documents"], stored["metadatas"]):
        if (text, meta) != expected[doc_id] or type(meta["activo"]) is not bool:
            raise CollectionError("Documentos o metadatos no coinciden con el corpus.")
        if json.loads(meta["tags_regionales_json"]) != documents[ids.index(doc_id)]["metadatos"]["tags_regionales"]:
            raise CollectionError("Tags almacenados inválidos.")


def ingest(client, documents: list[dict], model: str, embedding_function: GeminiEmbeddingFunction):
    ids, texts, metas = corpus_records(documents)
    try:
        existing = client.get_collection(COLLECTION_NAME, embedding_function=None)
    except NotFoundError:
        collection = client.get_or_create_collection(
            name=COLLECTION_NAME, metadata=collection_metadata(model),
            embedding_function=embedding_function,
        )
    else:
        validate_collection(existing, model, ids)
        collection = client.get_collection(COLLECTION_NAME, embedding_function=embedding_function)
    validate_collection(collection, model, ids)
    collection.upsert(ids=ids, documents=texts, metadatas=metas)
    verify_collection(collection, documents, model)
    return collection


def verify(client, documents: list[dict], model: str):
    collection = client.get_collection(COLLECTION_NAME, embedding_function=None)
    verify_collection(collection, documents, model)
    return collection


def check_event_record(collection, text: str, metadata: dict) -> None:
    record = collection.get(ids=["DOC-007"], include=["documents", "metadatas"])
    if (record["ids"] != ["DOC-007"] or record["documents"] != [text]
            or record["metadatas"] != [metadata]
            or type(record["metadatas"][0]["activo"]) is not bool
            or collection.count() != 15):
        raise HotEventError("Estado inesperado de DOC-007 o de la colección.")


def hot_event(client, documents: list[dict], model: str,
              embedding_function: GeminiEmbeddingFunction) -> None:
    """Retira temporalmente una solución y restaura la fuente en finally.

    add no corresponde a un ID existente; update requiere garantizar su existencia.
    upsert permite insertar o actualizar y repetir el flujo de forma idempotente.
    Las operaciones separadas no constituyen una transacción ni un bloqueo distribuido.
    """
    ids, texts, metas = corpus_records(documents)
    if "DOC-007" not in ids:
        raise HotEventError("DOC-007 no está en el corpus.")
    position = ids.index("DOC-007")
    text, original_metadata = texts[position], metas[position]
    if original_metadata["activo"] is not True:
        raise HotEventError("La fuente debe declarar DOC-007 activo.")
    existing = client.get_collection(COLLECTION_NAME, embedding_function=None)
    verify_collection(existing, documents, model)
    collection = client.get_collection(COLLECTION_NAME, embedding_function=embedding_function)
    check_event_record(collection, text, original_metadata)
    changed_metadata = dict(original_metadata)
    changed_metadata["activo"] = False
    applied = False
    original_error = None
    expected_errors = (ChromaError, ValueError, RuntimeError, OSError,
                       httpx.NetworkError, httpx.TimeoutException, errors.APIError)
    try:
        # documents implica un embedding documental, incluso sin cambiar el texto.
        collection.upsert(ids=["DOC-007"], documents=[text], metadatas=[changed_metadata])
        applied = True
        check_event_record(collection, text, changed_metadata)
        print("Evento en caliente sobre DOC-007.")
        print("Estado anterior: activo=true.")
        print("Operación aplicada: upsert.")
        print("Estado recuperado con get: activo=false.")
        print("Cantidad de documentos durante el evento: 15.")
        print("Cambio verificado: la solución quedó temporalmente fuera de vigencia.")
    except expected_errors as error:
        original_error = error
    finally:
        if not applied and original_error is not None:
            # Una operación puede persistirse y fallar antes de confirmar al cliente.
            # Si no se puede comprobar el estado, se intenta restaurar por seguridad.
            try:
                check_event_record(collection, text, original_metadata)
            except expected_errors:
                applied = True
        if applied:
            try:
                collection.upsert(ids=["DOC-007"], documents=[text], metadatas=[original_metadata])
                check_event_record(collection, text, original_metadata)
                verify_collection(collection, documents, model)
            except expected_errors as restoration_error:
                original_type = type(original_error).__name__ if original_error is not None else "ninguno"
                # Solo tipos de error: no se muestran mensajes remotos ni credenciales.
                raise RestorationError(
                    "No se puede garantizar la restauración. "
                    f"Error original: {original_type}; "
                    f"error de restauración: {type(restoration_error).__name__}."
                ) from restoration_error
            print("Restauración aplicada mediante upsert.")
            print("Estado final: activo=true.")
            print("Colección restaurada y verificada contra base_conocimiento.json.")
    if original_error is not None:
        raise original_error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("ingest", "verify", "hot-event"))
    args = parser.parse_args(argv)
    try:
        api_key, model, path = load_configuration(verify=args.command == "verify")
        documents = load_corpus()
        if args.command in ("verify", "hot-event") and not (path / "chroma.sqlite3").is_file():
            raise CollectionError("Base persistente inexistente; primero ejecutar ingest.")
        client = persistent_client(path)
        if args.command == "hot-event":
            function = GeminiEmbeddingFunction(model=model, api_key=api_key)
            hot_event(client, documents, model, function)
            return EXIT_OK
        if args.command == "ingest":
            function = GeminiEmbeddingFunction(model=model, api_key=api_key)
            collection = ingest(client, documents, model, function)
            print(f"Colección: {COLLECTION_NAME}")
            print("Cliente persistente: directorio configurado en CHROMA_DB_PATH")
            print("Operación: upsert")
            print("Documentos esperados: 15")
        else:
            collection = verify(client, documents, model)
            print("Colección persistente recargada.")
            print(f"Colección: {COLLECTION_NAME}")
        print(f"Documentos almacenados: {collection.count()}")
        print("IDs verificados: 15")
        print("Métrica: cosine")
        if args.command == "ingest":
            print("Ingesta persistente verificada.")
        else:
            print("Verificación local completada sin llamadas a la API.")
        return EXIT_OK
    except ConfigurationError:
        print("Error: configuración requerida ausente o incompatible.")
        return EXIT_CONFIGURATION
    except json.JSONDecodeError:
        print("Error: JSON inválido.")
        return EXIT_JSON
    except CorpusError:
        print("Error: corpus inválido.")
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
    except CollectionError as error:
        print(f"Error: {error}")
        return EXIT_CHROMA
    except (OSError, UnicodeError):
        print("Error: archivo o ruta inaccesible, o codificación inválida.")
        return EXIT_FILE
    except (ChromaError, ValueError, RuntimeError):
        print("Error: operación ChromaDB rechazada; revisar compatibilidad y almacenamiento.")
        return EXIT_CHROMA


if __name__ == "__main__":
    raise SystemExit(main())
