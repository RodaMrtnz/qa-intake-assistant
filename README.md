# QA Intake Assistant

Proyecto individual de Desarrollo de Sistemas de Inteligencia Artificial.

## Descripción

Asistente inteligente para clasificar reportes de defectos de software escritos en lenguaje natural por testers o usuarios. Identificará la intención y extraerá información técnica estructurada.

El LLM se limitará a interpretar el texto: no podrá inventar datos internos, decidir reglas de negocio ni modificar directamente información real.

El repositorio contiene únicamente la estructura inicial. Las Partes A, B y C y el pipeline están pendientes.

Autor: Rodrigo Martínez

## Tecnologías

La solución utilizará Python, Pydantic V2 y la API de OpenAI.

## Estructura del repositorio

```text
.
├── README.md             # Presentación e instrucciones iniciales
├── informe.md            # Encabezados del informe
├── schemas.py            # Futuros esquemas de datos
├── app.py                # Futuro punto de entrada de la aplicación
├── resultados_lote.md    # Tabla para seis pruebas
├── requirements.txt      # Dependencias iniciales
├── .env.example          # Variables de API key y modelo, sin valores
└── .gitignore            # Exclusiones de Git
```

## Preparación provisional del entorno

Desde la carpeta del proyecto, con Python instalado:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

En Linux o macOS, activar el entorno con `source .venv/bin/activate`.

Las variables `OPENAI_API_KEY` y `OPENAI_MODEL` están indicadas sin valores en `.env.example`. No se necesita una clave para esta inicialización.

Todavía no hay un pipeline implementado ni instrucciones de ejecución de la aplicación.
