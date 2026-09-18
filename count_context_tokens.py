"""Cuenta el corpus serializado con Gemini, sin generar contenido."""

import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from google import genai
from google.genai import errors


def main() -> int:
    api_key = ""
    try:
        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        model = os.getenv("GEMINI_MODEL", "").strip()
        if not api_key or not model:
            print("Error: se requieren GEMINI_API_KEY y GEMINI_MODEL.")
            return 1

        archivo = Path(__file__).resolve().parent / "base_conocimiento.json"
        # newline="" conserva los saltos de línea originales del archivo.
        with archivo.open("r", encoding="utf-8", newline="") as source:
            contenido_completo = source.read()

        with genai.Client(api_key=api_key) as client:
            resultado = client.models.count_tokens(
                model=model,
                contents=contenido_completo,
            )

        if resultado.total_tokens is None:
            print("Error: Gemini no devolvió total_tokens.")
            return 1

        # También protege la salida si una configuración incorrecta usa la clave
        # como nombre del modelo. Nunca muestra detalles de errores remotos.
        modelo_seguro = model.replace(api_key, "[REDACTADO]")
        print(f"Modelo utilizado: {modelo_seguro}")
        print(f"Archivo contado: {archivo.name}")
        print(f"Cantidad de caracteres: {len(contenido_completo)}")
        print(f"Cantidad de palabras: {len(contenido_completo.split())}")
        print(f"total_tokens: {resultado.total_tokens}")
        return 0
    except (OSError, UnicodeError):
        print("Error: no se pudo cargar la configuración o leer el archivo UTF-8.")
        return 1
    except (httpx.NetworkError, httpx.TimeoutException):
        print("Error: conexión o tiempo de espera agotado durante el conteo.")
        return 1
    except errors.APIError:
        print("Error: Gemini rechazó la solicitud de conteo de tokens.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
