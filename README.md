# QA Intake Assistant

Proyecto Integrador grupal de Desarrollo de Sistemas de Inteligencia Artificial.

## Descripción

Asistente inteligente para clasificar reportes de defectos de software escritos en lenguaje natural por testers o usuarios. Identificará la intención y extraerá información técnica estructurada.

El LLM se limitará a interpretar el texto: no podrá inventar datos internos, decidir reglas de negocio ni modificar directamente información real.

El repositorio contiene el diagnóstico, el brief técnico y un pipeline funcional que utiliza Gemini API y Pydantic para extraer y validar información estructurada. El lote de pruebas y la interfaz web se encuentran en desarrollo.

## Integrantes

- Rodrigo Martínez
- Nadia Alejandra Brizuela
- Francisco Heili
- Lucas Nicolas Grassi
- Fernando Gomez

## Tecnologías

La solución utilizará Python, Pydantic V2 y Gemini API.

## Estructura del repositorio

```text
.
├── README.md             # Presentación e instrucciones iniciales
├── informe.md            # Diagnóstico y brief técnico del proyecto
├── schemas.py            # Contrato y validaciones con Pydantic
├── app.py                # Pipeline de extracción y validación con Gemini
├── resultados_lote.md    # Tabla para seis pruebas
├── requirements.txt      # Dependencias de Python
├── .env.example          # Variables de Gemini, sin credenciales
└── .gitignore            # Exclusiones de Git
```

## Preparación del entorno

Desde la carpeta del proyecto, con Python instalado:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

En Linux o macOS, activar el entorno con `source .venv/bin/activate`.

La variable requerida para Gemini API es `GEMINI_API_KEY`. El modelo se configura mediante `GEMINI_MODEL`; `.env.example` propone `gemini-3.1-flash-lite` y no contiene credenciales.

El pipeline de extracción y validación está implementado. Para ejecutarlo se requiere configurar localmente la API key y el modelo de Gemini en un archivo `.env`.

## Ejecución

Con el entorno virtual activado y `.env` configurado:

```powershell
python app.py "Desde la versión 2.4, la aplicación se cierra al abrir el carrito en Android."
```

El programa envía el reporte a Gemini, valida la respuesta estructurada mediante Pydantic y muestra el JSON resultante en la terminal. En esta entrega todavía no se guardan datos en SQL ni se crean tickets reales.
