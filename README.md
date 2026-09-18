# QA Intake Assistant

Proyecto Integrador grupal de Desarrollo de Sistemas de Inteligencia Artificial.

## Descripción y alcance

Asistente para interpretar reportes de defectos escritos en lenguaje natural por testers o usuarios. La Entrega 1 implementa extracción estructurada con Gemini y validación con Pydantic. El LLM interpreta texto; no confirma tickets ni modifica directamente información real.

La Entrega 2 agrega 15 antecedentes académicos sintéticos, FAISS persistente, ChromaDB persistente, búsqueda híbrida con filtros nativos por plataforma y vigencia, ETL con purga semántica y tres Killer Queries. Los resultados no confirman tickets externos.

Las capas de extracción y recuperación se ejecutan por separado. No hay interfaz web, Jira, SQL de negocio, LangChain, orquestador RAG ni despliegue en nube integrados. El almacenamiento interno de ChromaDB no equivale al esquema SQL proyectado en Entrega 1. Tampoco hay reglas oficiales, directorio corporativo real o acciones de escritura de tickets implementadas.

## Integrantes

- Rodrigo Martínez
- Nadia Alejandra Brizuela
- Francisco Heili
- Lucas Nicolas Grassi
- Fernando Gomez

## Preparación del entorno

Se requiere **Python 3.11 o superior**. **Python 3.11 es la versión recomendada y verificada**; las dependencias actuales se validaron con esa versión. Para instalar paquetes y usar Gemini se necesita internet, una API key propia y acceso a los modelos configurados. Los modelos del ejemplo corresponden a la ejecución documentada; su disponibilidad y cuota dependen de la cuenta.

Cloná o descargá el repositorio y ejecutá todos los comandos desde su carpeta raíz.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
test -f .env || cp .env.example .env
```

Conservá cualquier .env existente y completá los valores localmente. Nunca publiques ni agregues .env a Git: está ignorado. Si PowerShell bloquea la activación, usá .\.venv\Scripts\python.exe en lugar de python sin cambiar la política del sistema; en Linux/macOS podés usar .venv/bin/python. Las dependencias tienen rangos explícitos: permiten actualizaciones compatibles, pero no fijan exactamente todo el árbol transitivo.

## Variables de entorno

| Variable | Ejemplo no secreto | Uso |
| --- | --- | --- |
| GEMINI_API_KEY | vacío en .env.example | Clave propia para extracción, conteo y embeddings; no se persiste en configuraciones vectoriales. |
| GEMINI_MODEL | gemini-3.1-flash-lite | Extracción de Entrega 1 y conteo opcional. |
| GEMINI_EMBEDDING_MODEL | gemini-embedding-001 | Embeddings de 768 dimensiones para FAISS, ChromaDB y ETL. |
| FAISS_INDEX_PATH | faiss_index/qa_knowledge.index | Índice FAISS; el manifiesto complementario usa extensión .meta.json. |
| CHROMA_DB_PATH | chroma_db | Directorio persistente de ChromaDB. |

Las rutas vectoriales relativas se resuelven desde la raíz del proyecto mediante pathlib. Los modos locales de FAISS necesitan modelo y ruta, pero no utilizan la clave para embeddings. vector_db.py verify necesita modelo y ruta y no exige clave. Las operaciones Gemini requieren credenciales. OpenAI no es el proveedor productivo actual.

## Estructura del repositorio

```text
.
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── app.py                         # Extracción con Gemini
├── schemas.py                     # Contrato DefectExtraction
├── batch_test.py                  # Seis pruebas de Entrega 1
├── token_analysis.py              # Comparación histórica de tokens
├── informe.md                     # PEAS, matriz y brief de Entrega 1
├── resultados_lote.md              # Evidencia real de Entrega 1
├── base_conocimiento.json          # Fuente limpia: 15 documentos
├── cosine_demo.py                 # Validación local NumPy en 2D
├── count_context_tokens.py         # Conteo oficial opcional del JSON
├── pipeline_vectorial.py           # Construcción/recarga FAISS
├── volatility_demo.py              # RAM frente a disco entre procesos
├── vector_db.py                    # Ingesta, verificación, evento, búsqueda
├── base_conocimiento_etl_sucia.json # Dataset controlado: 18 registros
├── etl_purga.py                    # Normalización, IDs y purga semántica
├── killer_queries.py               # Tres casos; cuatro consultas
├── informe_entrega2.md             # Partes A, B y C
└── resultados_killer_queries.md     # Evidencia real de Killer Queries
```

.env, .venv/, __pycache__/, faiss_index/ y chroma_db/ son locales e ignorados. Los directorios vectoriales se crean al construir/ingerir y no vienen en una clonación. Se regeneran el índice, manifiesto y archivos internos de ChromaDB; los dos JSON de corpus sí están versionados. La consigna externa no forma parte del repositorio.

## Orden recomendado de ejecución

Los comandos siguientes sirven con el entorno virtual activo en ambos sistemas. Las operaciones Gemini consumen cuota y pueden generar costo; no es necesario repetirlas para consultar la evidencia existente.

### 1. Entrega 1: extracción y análisis histórico

```powershell
python app.py "Desde la versión 2.4, la aplicación se cierra al abrir el carrito en Android."
python batch_test.py
python token_analysis.py
```

app.py llama a Gemini, valida con Pydantic y muestra JSON. batch_test.py realiza nuevas llamadas para seis casos; no crea tickets. token_analysis.py reproduce el análisis de tokens de Entrega 1: utiliza la codificación de gpt-4o como aproximación comparativa, no como tokenizador oficial de Gemini. La primera ejecución puede requerir internet para descargar el vocabulario de tiktoken; no utiliza GEMINI_API_KEY ni genera contenido. La salida real documentada fue 32 tokens en español y 30 en inglés.

### 2. Análisis local de Entrega 2

```powershell
python cosine_demo.py
```

Valida cálculos manuales con NumPy y vectores pedagógicos 2D, sin embeddings reales ni red.

### 3. Reconstrucción y recarga FAISS

```powershell
python pipeline_vectorial.py
python pipeline_vectorial.py --load-only
```

La primera construcción genera 15 embeddings documentales y persiste IndexFlatIP normalizado y manifiesto. El modo normal ejecuta tres consultas con embeddings de consulta incluso al reutilizar el índice. Una persistencia incompatible puede provocar reconstrucción controlada. --load-only recarga y valida localmente sin embeddings ni API; ante archivos ausentes o incompatibles falla sin reconstruir. Primero ejecutá el modo normal en una clonación.

### 4. Volatilidad: procesos separados

```powershell
python volatility_demo.py build-volatile
python volatility_demo.py check-volatile
python volatility_demo.py verify-persistent
```

build-volatile llama a Gemini para 15 embeddings documentales, construye solo en RAM y no escribe el índice. Ejecutá cada comando como un proceso separado. check-volatile comprueba localmente que no existe volatile_demo.index; verify-persistent recarga localmente el índice de la etapa 3. Ambos modos locales evitan embeddings y llamadas. La prueba no reinicia físicamente el equipo ni demuestra concurrencia distribuida.

### 5. Reconstrucción y pruebas ChromaDB

```powershell
python vector_db.py ingest
python vector_db.py verify
python vector_db.py hot-event
python vector_db.py search --query "La app se cierra al abrir la cesta después de agregar un artículo agotado." --platform android --n-results 3
```

ingest genera 15 embeddings documentales y carga los mismos IDs mediante upsert sin duplicarlos. verify es local y comprueba la cantidad, los 15 IDs, los documentos y los metadatos contra base_conocimiento.json, sin generar embeddings ni llamar a Gemini. Primero hay que ingerir en una clonación. Abrir PersistentClient puede actualizar archivos internos incluso durante verificaciones lógicas de lectura.

hot-event retira temporalmente DOC-007 con activo=false, verifica mediante get y restaura en finally. Hace escrituras y genera dos embeddings documentales porque ambos upsert incluyen el documento; si falla la restauración, informa que no puede garantizarla.

search genera un embedding de consulta. Aplica where nativo por plataforma (web, android, ios o desktop) y activo=true, sin postfiltrado Python. Muestra vecinos sintéticos, distancia y similitud (1 - distancia). Es inspección B.4: todavía no aplica el umbral de aceptación, no confirma tickets externos y no se integra automáticamente con app.py.

### 6. ETL controlado

```powershell
python etl_purga.py --threshold 0.15
```

Genera 18 embeddings documentales para base_conocimiento_etl_sucia.json, normaliza dos anomalías, resuelve una colisión y purga por distancia dentro del mismo proyecto, plataforma y módulo. Distancia 0.15 equivale a similitud 0.85: sirve para casi duplicados, no para aceptar consultas. Exige tres eliminaciones y coincidencia completa con la fuente limpia; un resultado distinto termina con error controlado.

No modifica el dataset de entrada, base_conocimiento.json, FAISS ni ChromaDB. Sin --output no crea archivos; opcionalmente --output resultado_etl.json escribe atómicamente un JSON nuevo después de validar, fuera de rutas protegidas. No hace falta otra copia limpia para reproducir la entrega.

### 7. Killer Queries

```powershell
python killer_queries.py
```

Requiere la colección de la etapa 5. Genera cuatro embeddings de consulta (uno por caso y un diagnóstico adicional crudo para Face ID), cero documentales y ninguna escritura de registros. El filtro productivo sigue siendo nativo. Aplica similitud inclusiva >= 0.70; sin candidatos aceptados responde exactamente: No tengo esa información. El diagnóstico sin filtros solo evidencia el riesgo y no produce la respuesta productiva. Devuelve 0 únicamente si pasan los tres casos; los fallos muestran la evidencia real. C.2 justifica el umbral para este corpus pequeño, no como garantía universal ni como integración en app.py.

### 8. Conteo opcional del contexto

```powershell
python count_context_tokens.py
```

Llama a Gemini exclusivamente con count_tokens sobre el JSON completo tal como está serializado. No genera contenido ni embeddings. No es necesario repetirlo para consultar la medición documentada; cambios de serialización o saltos de línea pueden alterar el conteo.

## Evidencia y límites

- [informe.md](informe.md): diagnóstico, PEAS, matriz y alcance de Entrega 1.
- [resultados_lote.md](resultados_lote.md): resultados reales y limitaciones semánticas del extractor.
- [informe_entrega2.md](informe_entrega2.md): cálculos, persistencia, evento, purga y coherencia C.1–C.3.
- [resultados_killer_queries.md](resultados_killer_queries.md): tabla y salida real de los tres casos.

Pydantic garantiza estructura, no verdad semántica ni existencia de tickets. Falta el orquestador que conecte extracción, recuperación, umbral y generación trazable. No se demostraron concurrencia distribuida ni transacciones multirregistro. Para producción hacen falta datos reales autorizados, calibración más amplia y controles de permisos y acciones.
