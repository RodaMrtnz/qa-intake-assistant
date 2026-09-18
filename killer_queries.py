"""B.6: tres Killer Queries sintéticas; importar no ejecuta consultas.

La ejecución real solicita cuatro embeddings RETRIEVAL_QUERY y cero documentales.
El umbral es preliminar para esta prueba, no una calibración de producción.
"""

import argparse
import json
import math
from numbers import Real

import vector_db as db

ACCEPTANCE_THRESHOLD = 0.70
NO_INFORMATION = "No tengo esa información."
EXIT_SEMANTIC_FAILURE = 10
QUERY_1 = (
    "Cuando mando al changuito una mercadería que ya no tiene existencias, "
    "la app se baja sola al querer revisar la compra."
)
QUERY_2 = (
    "Después de actualizar iOS, Face ID rechaza siempre el desbloqueo "
    "y obliga a registrar nuevamente el acceso biométrico."
)
QUERY_3 = "La impresora 3D industrial quema el filamento al calibrar la temperatura del extrusor."


def aplicar_umbral(resultados: list[dict]) -> list[dict] | str:
    """Acepta por score, conservando orden y sin consultar metadatos."""
    if not isinstance(resultados, list):
        raise db.SearchError("Resultados inválidos.")
    accepted = []
    for result in resultados:
        if not isinstance(result, dict):
            raise db.SearchError("Resultado inválido.")
        score = result.get("similitud_coseno")
        if isinstance(score, bool) or not isinstance(score, Real) or not math.isfinite(score):
            raise db.SearchError("Similitud inválida.")
        if score >= ACCEPTANCE_THRESHOLD:
            accepted.append(result)
    return accepted if accepted else NO_INFORMATION


def diagnostico_crudo(consulta: str, collection) -> list[dict]:
    """Solo evidencia diagnóstica; nunca construye la respuesta productiva."""
    response = collection.query(
        query_texts=[consulta], n_results=3, include=["metadatas", "distances"],
    )
    if not isinstance(response, dict):
        raise db.SearchError("Diagnóstico inválido.")
    rows = []
    for field in ("ids", "metadatas", "distances"):
        batches = response.get(field)
        if not isinstance(batches, list) or len(batches) != 1 or not isinstance(batches[0], list):
            raise db.SearchError("Estructuras diagnósticas inconsistentes.")
        rows.append(batches[0])
    if len({len(row) for row in rows}) != 1 or len(rows[0]) > 3:
        raise db.SearchError("Cantidades diagnósticas inconsistentes.")
    results = []
    for doc_id, metadata, distance in zip(*rows):
        if (not isinstance(doc_id, str) or not doc_id.strip()
                or not isinstance(metadata, dict) or isinstance(distance, bool)
                or not isinstance(distance, Real) or not math.isfinite(distance)):
            raise db.SearchError("Registro diagnóstico inválido.")
        results.append({"id": doc_id, "metadatos": metadata,
                        "distancia_coseno": float(distance),
                        "similitud_coseno": 1.0 - float(distance)})
    return results


def comprobar_metadatos(resultados: list[dict], plataforma: str) -> bool:
    """Aserción defensiva: un incumplimiento falla, nunca elimina registros."""
    return all(result["metadatos"].get("plataforma") == plataforma
               and result["metadatos"].get("activo") is True for result in resultados)


def mostrar_resultados(label: str, resultados: list[dict]) -> None:
    print(label)
    if not resultados:
        print("Sin vecinos recuperados.")
    for position, result in enumerate(resultados, 1):
        meta = result["metadatos"]
        print(f"{position}. ID={result['id']} | plataforma={meta.get('plataforma')} | "
              f"activo={meta.get('activo')} | distancia={result['distancia_coseno']:.6f} | "
              f"similitud={result['similitud_coseno']:.6f}")


def ejecutar_pruebas(collection) -> list[dict]:
    """Cuatro consultas de solo lectura; devuelve evidencia y aprobaciones."""
    cases = []
    for number, name, query, platform in (
        (1, "Poder semántico con jerga", QUERY_1, "android"),
        (2, "El metadato salva el día", QUERY_2, "ios"),
        (3, "Fuera del catálogo", QUERY_3, "desktop"),
    ):
        print(f"\nCaso {number} — {name}")
        print(f"Consulta: {query}")
        raw = []
        if number == 2:
            print("Diagnóstico semántico crudo, sin where; no es una búsqueda productiva.")
            raw = diagnostico_crudo(query, collection)
            mostrar_resultados("Vecinos crudos (sin postfiltrado):", raw)
            antecedent = next(((i, r) for i, r in enumerate(raw, 1) if r["id"] == "DOC-003"), None)
            if antecedent is None:
                print("DOC-003 no apareció en el diagnóstico.")
            else:
                position, record = antecedent
                print(f"DOC-003: posición={position}; similitud={record['similitud_coseno']:.6f}.")
        _, where = db.search_parameters(query, platform, True, 3)
        print("Filtro productivo nativo: " + json.dumps(where, ensure_ascii=False))
        results = db.buscar_defectos(
            query_semantica=query, plataforma=platform, solo_activos=True,
            n_resultados=3, collection=collection,
        )
        mostrar_resultados("Vecinos productivos recibidos:", results)
        functional = aplicar_umbral(results)
        metadata_ok = comprobar_metadatos(results, platform)
        reasons = []
        if not metadata_ok:
            reasons.append("Un vecino productivo viola plataforma/activo; no fue ocultado.")
        if number == 1:
            expectation = "DOC-001 top-1 con similitud >= 0.70; todos Android y activos."
            if not results or results[0]["id"] != "DOC-001":
                reasons.append("DOC-001 no fue top-1.")
            if not results or results[0]["similitud_coseno"] < ACCEPTANCE_THRESHOLD:
                reasons.append("El top-1 no alcanzó 0.70.")
        elif number == 2:
            expectation = (
                "DOC-003 inactivo y predominante en diagnóstico; excluido del flujo iOS activo; "
                "sin resultados aceptados, abstención."
            )
            # Criterio explícito: predominante significa top-1 y score >= 0.70.
            if (not raw or raw[0]["id"] != "DOC-003"
                    or raw[0]["metadatos"].get("activo") is not False
                    or raw[0]["similitud_coseno"] < ACCEPTANCE_THRESHOLD):
                reasons.append("El diagnóstico no mostró DOC-003 inactivo como top-1 relevante (>= 0.70).")
            if any(r["id"] == "DOC-003" for r in results):
                reasons.append("DOC-003 apareció en la consulta productiva.")
        else:
            expectation = "Ningún vecino alcanza 0.70; responder: " + NO_INFORMATION
            if functional != NO_INFORMATION:
                reasons.append("Un vecino alcanzó el umbral en una consulta fuera del catálogo.")
        print(f"Expectativa: {expectation}")
        print("Resultado funcional final:")
        if not metadata_ok:
            print("Fallo de integridad del filtro; no se emite una recomendación.")
        elif isinstance(functional, str):
            print(functional)
        else:
            print("Antecedentes sintéticos aceptados: " + ", ".join(r["id"] for r in functional))
        passed = not reasons
        reason = " ".join(reasons) if reasons else "Se cumplieron todas las expectativas del caso."
        print("PASÓ" if passed else "NO PASÓ")
        print("Motivo: " + reason)
        cases.append({"caso": number, "resultados": results, "diagnostico": raw,
                      "respuesta": functional, "paso": passed, "motivo": reason})
    return cases


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    try:
        api_key, model, path = db.load_configuration()
        if not (path / "chroma.sqlite3").is_file():
            raise db.CollectionError("Base persistente inexistente.")
        documents = db.load_corpus()
        client = db.persistent_client(path)
        # Reutiliza validación completa de modelo, métrica, documentos y metadatos.
        db.verify(client, documents, model)
        function = db.GeminiEmbeddingFunction(model=model, api_key=api_key)
        collection = client.get_collection(db.COLLECTION_NAME, embedding_function=function)
        print("Corpus académico sintético; no confirma tickets externos.")
        print(f"Umbral preliminar de aceptación: {ACCEPTANCE_THRESHOLD:.2f}")
        cases = ejecutar_pruebas(collection)
        print("Consultas completadas: 4; embeddings documentales generados: 0.")
        code = db.EXIT_OK if all(case["paso"] for case in cases) else EXIT_SEMANTIC_FAILURE
    except db.ConfigurationError:
        print("Error: configuración ausente o incompatible.")
        code = db.EXIT_CONFIGURATION
    except json.JSONDecodeError:
        print("Error: JSON inválido.")
        code = db.EXIT_JSON
    except db.CorpusError:
        print("Error: corpus inválido.")
        code = db.EXIT_CORPUS
    except db.EmbeddingError:
        print("Error: embeddings inválidos.")
        code = db.EXIT_EMBEDDINGS
    except (db.httpx.NetworkError, db.httpx.TimeoutException):
        print("Error: conexión o timeout con Gemini.")
        code = db.EXIT_NETWORK
    except db.errors.APIError:
        print("Error: Gemini rechazó la consulta.")
        code = db.EXIT_API
    except (db.CollectionError, db.ChromaError, ValueError, RuntimeError, TypeError, KeyError):
        print("Error: colección o estructuras de resultados inválidas.")
        code = db.EXIT_CHROMA
    except (OSError, UnicodeError):
        print("Error: archivo o ruta inaccesible.")
        code = db.EXIT_FILE
    print(f"Código de salida: {code}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
