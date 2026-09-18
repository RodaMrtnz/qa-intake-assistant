"""Demostración 2D con vectores manuales, sin red ni credenciales."""

import numpy as np


def similitud_coseno(a: np.ndarray, b: np.ndarray) -> float:
    norma_a = float(np.linalg.norm(a))
    norma_b = float(np.linalg.norm(b))
    if norma_a == 0.0 or norma_b == 0.0:
        raise ValueError("La similitud coseno no está definida para vectores cero.")
    return float(np.dot(a, b) / (norma_a * norma_b))


def main() -> int:
    documentos = {
        "DOC-001": np.array([1.0, 9.0]),
        "DOC-002": np.array([9.0, 1.0]),
        "DOC-003": np.array([8.0, 2.0]),
    }
    consulta = np.array([9.0, 1.0])
    esperados = {"DOC-001": 0.219512, "DOC-002": 1.000000, "DOC-003": 0.990992}
    resultados = []
    for doc_id, vector in documentos.items():
        punto = float(np.dot(vector, consulta))
        norma_doc = float(np.linalg.norm(vector))
        norma_consulta = float(np.linalg.norm(consulta))
        denominador = norma_doc * norma_consulta
        similitud = similitud_coseno(vector, consulta)
        if not np.isclose(similitud, esperados[doc_id], rtol=0.0, atol=1e-6):
            print(f"Error: resultado inesperado para {doc_id}.")
            return 1
        resultados.append((doc_id, punto, norma_doc, norma_consulta, denominador, similitud))

    for a, b in ((np.zeros(2), consulta), (consulta, np.zeros(2))):
        try:
            similitud_coseno(a, b)
        except ValueError:
            continue
        print("Error: un vector cero no fue rechazado.")
        return 1

    print("Eje X: autenticación y acceso; eje Y: compras y carrito.")
    print("Consulta: No puedo ingresar, recibo un error de acceso. Vector: [9, 1]")
    print("ID | Producto punto | Norma documento | Norma consulta | Denominador | Similitud")
    for fila in sorted(resultados, key=lambda item: item[-1], reverse=True):
        print(f"{fila[0]} | " + " | ".join(f"{valor:.6f}" for valor in fila[1:]))
    print("Comprobaciones np.isclose: OK; rechazo de vectores cero: OK.")
    print("Umbral preliminar 2D: 0.70. DOC-003 es inactivo y no debe recomendarse.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
