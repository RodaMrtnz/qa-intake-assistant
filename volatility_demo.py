"""A.5: demostración de volatilidad; build-volatile consume embeddings reales.

Ejecutar build-volatile y check-volatile en procesos separados.
Los dos modos locales no crean clientes ni generan embeddings.
"""

import argparse
import json
from pathlib import Path

import faiss
import httpx
from google import genai
from google.genai import errors

import pipeline_vectorial as pipeline


def volatile_path(index_path: Path) -> Path:
    return index_path.parent / "volatile_demo.index"


def require_no_volatile_file(path: Path) -> None:
    if path.exists():
        raise pipeline.StorageError("Existe un volatile_demo.index inesperado.")


def build_volatile() -> None:
    api_key, model, index_path = pipeline.load_configuration()
    path = volatile_path(index_path)
    require_no_volatile_file(path)
    documents, _ = pipeline.load_corpus(pipeline.ROOT / "base_conocimiento.json")
    with genai.Client(api_key=api_key) as client:
        vectors = pipeline.embed_documents(documents, client, model)
    index = faiss.IndexFlatIP(pipeline.DIMENSION)
    index.add(vectors)
    if index.d != pipeline.DIMENSION or index.ntotal != 15:
        raise pipeline.StorageError("Dimensión o cantidad del índice volátil inválidas.")
    require_no_volatile_file(path)
    print("Índice volátil construido únicamente en RAM.")
    print(f"Dimensión: {index.d}; ntotal: {index.ntotal}.")
    print("Embeddings documentales generados en esta ejecución: 15.")
    print("No se llamó a faiss.write_index().")
    print("El proceso finalizará sin persistir volatile_demo.index.")


def check_volatile() -> None:
    # Usa la ruta configurada sin exigir ni utilizar credenciales.
    _api_key, _model, index_path = pipeline.load_configuration(load_only=True)
    del _api_key
    require_no_volatile_file(volatile_path(index_path))
    print("Proceso nuevo: volatile_demo.index no existe.")
    print("El índice construido solo en RAM no sobrevivió al reinicio del proceso.")
    print("Para reconstruirlo sería necesario volver a generar los embeddings documentales.")


def verify_persistent() -> None:
    _api_key, model, index_path = pipeline.load_configuration(load_only=True)
    del _api_key
    documents, corpus_hash = pipeline.load_corpus(pipeline.ROOT / "base_conocimiento.json")
    manifest = pipeline.expected_manifest(documents, model, corpus_hash)
    index = pipeline.load_index(index_path, manifest)
    print("Índice persistente recargado desde disco.")
    print(f"Dimensión: {index.d}; ntotal: {index.ntotal}.")
    print("Embeddings documentales generados en esta ejecución: 0.")
    print("Recarga verificada sin llamadas a la API.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build-volatile", "check-volatile", "verify-persistent"))
    args = parser.parse_args(argv)
    try:
        commands = {
            "build-volatile": build_volatile,
            "check-volatile": check_volatile,
            "verify-persistent": verify_persistent,
        }
        commands[args.command]()
        return pipeline.EXIT_OK
    except pipeline.ConfigurationError:
        print("Error: configuración requerida ausente.")
        return pipeline.EXIT_CONFIGURATION
    except json.JSONDecodeError:
        print("Error: JSON del corpus inválido.")
        return pipeline.EXIT_JSON
    except pipeline.CorpusError:
        print("Error: corpus inválido.")
        return pipeline.EXIT_CORPUS
    except pipeline.EmbeddingError:
        print("Error: embeddings inválidos.")
        return pipeline.EXIT_EMBEDDINGS
    except (httpx.NetworkError, httpx.TimeoutException):
        print("Error: conexión o timeout con Gemini.")
        return pipeline.EXIT_NETWORK
    except errors.APIError:
        print("Error: Gemini rechazó la solicitud de embeddings.")
        return pipeline.EXIT_API
    except pipeline.StorageError:
        print("Error: persistencia inválida o volatile_demo.index inesperado.")
        return pipeline.EXIT_STORAGE
    except (OSError, UnicodeError):
        print("Error: archivo inexistente, ilegible o con codificación inválida.")
        return pipeline.EXIT_FILE
    except RuntimeError:
        print("Error: operación FAISS fallida.")
        return pipeline.EXIT_STORAGE


if __name__ == "__main__":
    raise SystemExit(main())
