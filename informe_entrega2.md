# TP Integrador — Entrega 2

## Parte A — Embeddings y búsqueda semántica

### A.1 — Autopsia del contexto estático

QA Intake Assistant interpreta reportes de defectos y valida sus datos; el prototipo de Entrega 1 no incorpora toda la base al prompt ni implementa recuperación. Aquí se analiza el escenario de enviar como contexto estático la base de 15 defectos históricos sintéticos y sus soluciones académicas. No son tickets reales ni validan los datos alucinados de la Entrega 1.

| Problema | Aplicación a QA Intake Assistant |
| --- | --- |
| Desangre de tokens | Reenviar los 15 documentos en cada consulta repite 4.756 tokens de corpus, aunque la pregunta requiera un único antecedente. Además del costo, aumenta la latencia y el consumo de contexto. |
| Lost in the Middle | Para una consulta sobre el error 401 de autenticación, el antecedente puede quedar rodeado por documentos de carrito, promociones, notificaciones, reportes y formularios. Al crecer el bloque, la atención sobre el dato pertinente puede volverse menos controlable, verificable y eficiente; no significa que el modelo siempre falle. La recuperación vectorial permite seleccionar primero los documentos con mayor afinidad. |
| Inconsistencia de estado concurrente | Una copia vieja del contexto puede seguir recomendando un procedimiento después de quedar obsoleto. `DOC-003`, `DOC-005` y `DOC-014` están inactivos y no deben recomendarse como soluciones vigentes. Una base externa actualizada permite consultar el estado actual en cada búsqueda y aplicar el filtro de vigencia. `activo` representa la vigencia del conocimiento, no si el ticket sigue abierto: un defecto resuelto puede tener una solución todavía recomendable. |

#### Desangre de tokens: medición y costo

Las 15 `descripcion_semantica` suman **1.818 palabras**. El corpus JSON completo contado contiene **18.606 caracteres**, **2.244 palabras** y **4.756 tokens**.
El conteo oficial se obtuvo ejecutando localmente `count_context_tokens.py`, mediante `client.models.count_tokens`, con **`gemini-3.1-flash-lite`**, el **18 de septiembre de 2026**. La medición se ejecutó localmente una única vez y su resultado se documenta a continuación.

```text
Modelo utilizado: gemini-3.1-flash-lite
Archivo contado: base_conocimiento.json
Cantidad de caracteres: 18606
Cantidad de palabras: 2244
total_tokens: 4756
```

Se usa la tarifa estándar paga de entrada de **USD 0,25 por millón de tokens**, según la [documentación oficial de precios de Gemini](https://ai.google.dev/gemini-api/docs/pricing), consultada el **18 de septiembre de 2026**.

```text
Costo por consulta = 4.756 / 1.000.000 × USD 0,25
                   = USD 0,001189

Costo diario para 500 consultas = USD 0,001189 × 500
                                 = USD 0,5945

Costo para 30 días = USD 0,5945 × 30
                   = USD 17,835
```

El nivel gratuito no cobra tokens, pero tiene límites de uso. El cálculo pago muestra cómo escala el costo y representa únicamente el reenvío del corpus: no incluye System Prompt, consulta del usuario, historial, otros mensajes ni salida. Por lo tanto, no es el costo total de la aplicación.
Enviar toda la base también aumenta latencia y consumo de contexto. En una futura base vectorial, los documentos se vectorizan al cargarlos o actualizarlos y cada consulta recupera únicamente los fragmentos relevantes; habrá que contabilizar por separado el costo de embeddings y de generación.

#### Cierre de A.1

`SELECT ... WHERE descripcion LIKE '%...%'` busca coincidencias textuales, no similitud de significado.
Una búsqueda de `login` no encuentra automáticamente `inicio de sesión`, `acceso` o `ingreso`, aunque expresen la misma intención; requiere reglas adicionales para sinónimos y jerga.

### A.2 — Similitud coseno a mano

Se reduce el dominio a dos ejes conceptuales: **X**, afinidad con autenticación y acceso; **Y**, afinidad con compras y carrito. Los valores se asignaron manualmente con finalidad pedagógica: **no son embeddings reales ni fueron generados por Gemini**.

| Elemento | Significado | Vector [X, Y] |
| --- | --- | --- |
| DOC-001 | Cierre del carrito | [1, 9] |
| DOC-002 | Error 401 de autenticación | [9, 1] |
| DOC-003 | Acceso biométrico; documento inactivo | [8, 2] |
| Consulta | «No puedo ingresar, recibo un error de acceso» | [9, 1] |

La similitud compara la orientación de los vectores:

```text
similitud(A, B) = (A · B) / (||A|| × ||B||)
||[x, y]|| = sqrt(x² + y²)
```

#### Desarrollo manual

La norma de la consulta Q = [9, 1] es `sqrt(9² + 1²) = sqrt(82) ≈ 9,055385`.

**DOC-001, A = [1, 9]:**

```text
A · Q = 1 × 9 + 9 × 1 = 18
||A|| = sqrt(1² + 9²) = sqrt(82) ≈ 9,055385
||Q|| = sqrt(82) ≈ 9,055385
Denominador = sqrt(82) × sqrt(82) = 82
Similitud = 18 / 82 ≈ 0,219512
```

**DOC-002, A = [9, 1]:**

```text
A · Q = 9 × 9 + 1 × 1 = 82
||A|| = sqrt(9² + 1²) = sqrt(82) ≈ 9,055385
||Q|| = sqrt(82) ≈ 9,055385
Denominador = sqrt(82) × sqrt(82) = 82
Similitud = 82 / 82 = 1,000000
```

**DOC-003, A = [8, 2]:**

```text
A · Q = 8 × 9 + 2 × 1 = 74
||A|| = sqrt(8² + 2²) = sqrt(68) ≈ 8,246211
||Q|| = sqrt(82) ≈ 9,055385
Denominador = sqrt(68) × sqrt(82) = sqrt(5576) ≈ 74,672619
Similitud = 74 / sqrt(5576) ≈ 0,990992
```

#### Validación con NumPy

Salida real de `python cosine_demo.py`, ejecutado en el entorno virtual con NumPy 2.4.6; código de salida **0**:

```text
Eje X: autenticación y acceso; eje Y: compras y carrito.
Consulta: No puedo ingresar, recibo un error de acceso. Vector: [9, 1]
ID | Producto punto | Norma documento | Norma consulta | Denominador | Similitud
DOC-002 | 82.000000 | 9.055385 | 9.055385 | 82.000000 | 1.000000
DOC-003 | 74.000000 | 8.246211 | 9.055385 | 74.672619 | 0.990992
DOC-001 | 18.000000 | 9.055385 | 9.055385 | 82.000000 | 0.219512
Comprobaciones np.isclose: OK; rechazo de vectores cero: OK.
Umbral preliminar 2D: 0.70. DOC-003 es inactivo y no debe recomendarse.
```

El script comprueba los tres scores aproximados con `np.isclose`, usando tolerancia absoluta `1e-6`, y verifica que un vector cero en cualquiera de las posiciones produzca `ValueError`: su norma haría nulo el denominador.

#### Reflexión sobre el umbral y la vigencia

El umbral **0,70** es preliminar y exclusivo de esta demostración 2D; deberá recalibrarse con embeddings reales y Killer Queries.
Si ningún resultado supera el umbral, el sistema debe responder **«No tengo esa información.»**, sin forzar el vecino más cercano.
`DOC-003` es cercano semánticamente, pero `activo=false` impide recomendarlo: esto anticipa el filtro obligatorio **`activo=true`** en B.4, que todavía no se implementó.

### A.3 — Base de conocimiento documental

`base_conocimiento.json` contiene 15 antecedentes sintéticos y creíbles de QA, con problemas históricos y soluciones verificadas dentro de escenarios académicos ficticios; no son tickets reales. Cada documento separa `descripcion_semantica`, que se vectoriza, de `metadatos`, destinados a futuros filtros duros.

Según la Regla del Arquitecto, lo narrativo queda en el texto y los campos de filtrado en metadatos. `descripcion_semantica` conserva contexto, reproducción, resultado esperado, resultado real y solución. `proyecto`, `plataforma`, `modulo`, `activo`, `defect_id` y `estado_defecto` son metadatos; `tags_regionales` conserva sinónimos y jerga auxiliar. `activo` representa la vigencia del conocimiento, no el estado abierto o cerrado del ticket: una solución de un defecto resuelto puede seguir siendo válida.

| Dimensión | Distribución |
| --- | --- |
| Proyecto | 5 `tienda_web`, 4 `portal_clientes`, 4 `banca_movil`, 2 `gestion_interna` |
| Plataforma | 5 `android`, 5 `web`, 3 `ios` (iOS), 2 `desktop` |
| Vigencia | 12 activos y 3 inactivos: `DOC-003`, `DOC-005` y `DOC-014` |

### A.4 — Índice FAISS persistente

`pipeline_vectorial.py` utiliza el modelo `gemini-embedding-001`, leído de `GEMINI_EMBEDDING_MODEL`, con dimensión 768. El corpus usa `RETRIEVAL_DOCUMENT` y las consultas usan `RETRIEVAL_QUERY`. Se valida cantidad, dimensión, valores finitos y ausencia de vectores cero; los embeddings se convierten a `float32` y se normalizan mediante `faiss.normalize_L2`.

El índice es `IndexFlatIP`: con vectores normalizados, el producto interno equivale a **similitud coseno**, donde un valor mayor indica mayor afinidad. Se reporta por separado **`distancia_coseno = 1 - similitud_coseno`**; el producto interno no se denomina distancia.

La persistencia usa `faiss.write_index` y la recarga usa `faiss.read_index`. El manifiesto complementario incluye versión del formato, modelo, dimensión, tipo de índice, métrica, IDs ordenados, cantidad de documentos y SHA-256 del contenido completo del corpus. Al recargar se comprueban esos datos y las propiedades del índice; si dejan de coincidir, o falta uno de los archivos, el modo normal informa el motivo y regenera de forma controlada. `--load-only` rechaza una persistencia inválida sin regenerar ni conectarse a la API.

El índice `faiss_index/qa_knowledge.index` y el manifiesto `faiss_index/qa_knowledge.meta.json` se escriben primero en archivos temporales del mismo directorio y se reemplazan mediante `os.replace`. Son artefactos regenerables ignorados por Git; **`base_conocimiento.json` es la fuente de verdad versionada** del corpus sintético. Las posiciones FAISS se corresponden con el orden documental validado por el manifiesto.

#### Resultados de la ejecución real

Se ejecutó búsqueda semántica pura top-3 para las tres consultas de prueba. Los resultados no confirman la existencia de tickets fuera del corpus sintético.

| Consulta | Ranking | Documento | Activo | Similitud coseno | Distancia coseno |
| --- | ---: | --- | --- | ---: | ---: |
| Cierre al abrir la cesta después de agregar un artículo agotado | 1 | DOC-001 | true | 0.801476 | 0.198524 |
| Cierre al abrir la cesta después de agregar un artículo agotado | 2 | DOC-004 | true | 0.689533 | 0.310467 |
| Cierre al abrir la cesta después de agregar un artículo agotado | 3 | DOC-007 | true | 0.670791 | 0.329209 |
| Login 401 después de renovar una sesión vencida | 1 | DOC-002 | true | 0.802261 | 0.197739 |
| Login 401 después de renovar una sesión vencida | 2 | DOC-008 | true | 0.721380 | 0.278620 |
| Login 401 después de renovar una sesión vencida | 3 | DOC-009 | true | 0.631003 | 0.368997 |
| Botón Guardar bloqueado después de corregir un campo inválido | 1 | DOC-015 | true | 0.799975 | 0.200025 |
| Botón Guardar bloqueado después de corregir un campo inválido | 2 | DOC-003 | false | 0.643128 | 0.356872 |
| Botón Guardar bloqueado después de corregir un campo inválido | 3 | DOC-002 | true | 0.634907 | 0.365093 |

En las tres consultas el documento esperado quedó primero, con scores top-1 de `0.801476`, `0.802261` y `0.799975`. Los resultados secundarios son semánticamente cercanos, pero no necesariamente aplicables. `DOC-003` apareció segundo en la tercera consulta pese a estar inactivo: no es un fallo de A.4, que realiza búsqueda semántica pura sin filtrar vigencia. El caso demuestra por qué B.4 necesitará filtrar `activo=true` dentro de la consulta de ChromaDB, no mediante post-filtering de los vecinos ya recuperados.

#### Evidencia de persistencia

```text
Primera ejecución:
Índice FAISS construido y persistido. Embeddings documentales generados: 15.

Recarga local:
Dimensión: 768; ntotal: 15; modelo: gemini-embedding-001
SHA-256 del corpus coincidente.
Recarga local verificada sin llamadas a la API.
```

Esta evidencia demuestra construcción y recarga para A.4. La prueba destructiva específica de A.5 se documenta por separado a continuación. No se implementaron ChromaDB ni los componentes de la Parte B.

### A.5 — Prueba destructiva: volatilidad de la RAM

La prueba se ejecutó localmente usando procesos separados de Python para simular el final y reinicio del entorno de ejecución. No se reinició físicamente Windows ni un servidor: la memoria del proceso finalizado no está disponible para el siguiente.

1. `build-volatile` generó nuevamente los 15 embeddings documentales reales mediante `RETRIEVAL_DOCUMENT` y construyó un `IndexFlatIP` de 768 dimensiones únicamente en memoria.
2. No llamó a `faiss.write_index()` ni creó `volatile_demo.index`. Al finalizar ese proceso de Python, la instancia del índice en RAM desapareció.
3. `check-volatile`, ejecutado como un proceso nuevo, confirmó que no existía un archivo recuperable del índice volátil. Para reconstruirlo con este procedimiento sería necesario generar otra vez los embeddings, consumiendo nuevamente tokens o cuota y pudiendo generar costo en un nivel pago.
4. `verify-persistent` recargó desde disco el índice real de A.4, con dimensión 768 y `ntotal=15`, sin generar embeddings documentales ni de consulta y sin llamadas a la API.

| Etapa | Persistencia | Embeddings generados | Resultado |
| --- | --- | ---: | --- |
| Construcción volátil | Solo RAM | 15 | Índice disponible mientras vivía el proceso |
| Proceso nuevo | Sin archivo persistido | 0 | El índice volátil ya no estaba disponible |
| Recarga persistente | Disco mediante FAISS | 0 | Índice de 768 dimensiones y 15 documentos recuperado |

#### Salidas reales

```text
> python .\volatility_demo.py build-volatile
Índice volátil construido únicamente en RAM.
Dimensión: 768; ntotal: 15.
Embeddings documentales generados en esta ejecución: 15.
No se llamó a faiss.write_index().
El proceso finalizará sin persistir volatile_demo.index.
Código de salida: 0
```

```text
> python .\volatility_demo.py check-volatile
Proceso nuevo: volatile_demo.index no existe.
El índice construido solo en RAM no sobrevivió al reinicio del proceso.
Para reconstruirlo sería necesario volver a generar los embeddings documentales.
Código de salida: 0
```

```text
> python .\volatility_demo.py verify-persistent
Índice persistente recargado desde disco.
Dimensión: 768; ntotal: 15.
Embeddings documentales generados en esta ejecución: 0.
Recarga verificada sin llamadas a la API.
Código de salida: 0
```

Los tres comandos finalizaron con código de salida `0`. La comprobación adicional confirmó la ausencia del archivo:

```text
> Test-Path .\faiss_index\volatile_demo.index
False
```

No se creó `volatile_demo.index`. El índice persistente `qa_knowledge.index` y su manifiesto permanecieron intactos. Los binarios y el manifiesto regenerable siguen ignorados y no se versionan; la fuente de verdad del corpus sintético continúa siendo `base_conocimiento.json`. Esta prueba demuestra volatilidad y recarga entre procesos, no atomicidad, concurrencia ni filtrado híbrido, que corresponden a la Parte B.

#### Reflexión de producción

En producción, un reinicio elimina cualquier índice que exista solamente en RAM, obligando a reconstruirlo y repitiendo costo, cuota y latencia.
Con dos servidores, cada memoria es independiente; guardar una copia local reduce regeneraciones, pero para consistencia y concurrencia se necesita almacenamiento compartido o una base vectorial persistente como ChromaDB con una arquitectura adecuada para ese acceso.

## Parte B — ChromaDB, filtrado híbrido y ETL

### B.1 — Migración a ChromaDB

Se utilizó ChromaDB **1.5.9** mediante `chromadb.PersistentClient`, no el cliente volátil. `vector_db.py` obtiene la ruta desde `CHROMA_DB_PATH` y resuelve las rutas relativas respecto de la raíz del proyecto. La colección `qa_intake_knowledge` se configuró con `metadata={"hnsw:space": "cosine"}`; la implementación también verifica que la configuración HNSW efectiva use `space="cosine"`.

Se migraron los mismos 15 documentos de `base_conocimiento.json` mediante una operación `collection.upsert`, no `add`. `upsert` permite repetir la ingesta actualizando los mismos IDs sin duplicarlos. La colección persistente queda en `chroma_db/`, ignorada por Git. `base_conocimiento.json` continúa siendo la fuente de verdad versionada del corpus sintético y permite reconstruir la colección.

#### Función de embeddings personalizada

`GeminiEmbeddingFunction` utiliza `gemini-embedding-001` con dimensión 768. La ingesta mediante `upsert` usa `RETRIEVAL_DOCUMENT`; una futura consulta con `query_texts` utiliza `embed_query` y `RETRIEVAL_QUERY`. Se valida cantidad, dimensión, valores finitos y ausencia de vectores cero; los vectores se convierten a `float32` y se normalizan de forma coherente con A.4.

El cliente Gemini se crea de manera perezosa, únicamente al solicitar embeddings. La configuración persistida de la función se limita al modelo y la dimensión: no contiene la API key. Su reconstrucción obtiene la clave del entorno cuando corresponda, sin guardarla en la base. El modo `verify` obtiene la colección con `embedding_function=None` y utiliza `get/count`, sin crear clientes Gemini ni necesitar una clave para generar embeddings.

#### Transformación documental

| Elemento de `base_conocimiento.json` | Representación en ChromaDB |
| --- | --- |
| `id` | ID del registro |
| `descripcion_semantica` | Documento vectorizado |
| `proyecto` | Metadato escalar |
| `plataforma` | Metadato escalar filtrable |
| `modulo` | Metadato escalar |
| `activo` | Booleano real y metadato filtrable |
| `defect_id` | Metadato escalar |
| `estado_defecto` | Metadato escalar |
| `tags_regionales` | JSON serializado en `tags_regionales_json` |

`tags_regionales` se serializa mediante `json.dumps(tags, ensure_ascii=False)` porque es una lista auxiliar de sinónimos y jerga, no el filtro duro principal. `activo` no se convierte en texto: B.4 deberá filtrarlo mediante un booleano real. La ingesta rechaza colecciones con métrica, modelo, dimensión, schema o IDs adicionales incompatibles, solicitando una migración explícita; no las elimina silenciosamente.

#### Evidencia real de ingesta y recarga

```text
> python .\vector_db.py ingest
Colección: qa_intake_knowledge
Cliente persistente: directorio configurado en CHROMA_DB_PATH
Operación: upsert
Documentos esperados: 15
Documentos almacenados: 15
IDs verificados: 15
Métrica: cosine
Ingesta persistente verificada.
Código de salida: 0
```

```text
> python .\vector_db.py verify
Colección persistente recargada.
Colección: qa_intake_knowledge
Documentos almacenados: 15
IDs verificados: 15
Métrica: cosine
Verificación local completada sin llamadas a la API.
Código de salida: 0
```

`ingest` realizó la llamada de embeddings y persistió los registros. `verify`, ejecutado en otro proceso, recuperó 15 registros sin generar embeddings ni llamar a Gemini. Ambas ejecuciones terminaron con código `0`. Esto prueba la persistencia de la colección, pero todavía no constituye la búsqueda híbrida de B.4.

### B.2 — Los tres límites de FAISS que ChromaDB resuelve

| Límite de FAISS | Cómo se manifiesta en QA Intake Assistant | Cómo lo resuelve ChromaDB |
| --- | --- | --- |
| Sin persistencia transaccional o atomicidad | FAISS serializa el índice completo mediante `write_index`, pero ese archivo no constituye por sí mismo una base transaccional. En A.4 se guardan por separado índice y manifiesto, se validan con el hash del corpus y se regenera si quedan incompatibles. Una interrupción entre las escrituras puede dejar un par inconsistente, aunque cada reemplazo individual sea atómico. | ChromaDB administra documentos, embeddings y metadatos dentro de una colección persistente y expone operaciones como `upsert`. Ofrece una capa de almacenamiento más apropiada que un archivo FAISS aislado; esta entrega no demuestra garantías distribuidas ni atomicidad bajo fallos. |
| Sin filtrado híbrido nativo | FAISS devuelve vecinos por posición y similitud, pero no conoce `plataforma`, `activo`, `proyecto` o `modulo`. En A.4 apareció `DOC-003` pese a estar inactivo porque la búsqueda fue puramente semántica. | ChromaDB almacena metadatos junto con los documentos y permite aplicar un `where` nativo durante la consulta. Esto posibilitará exigir `activo=true` y una plataforma determinada al recuperar resultados. Se implementará y demostrará en B.4; aún no se presenta como una prueba ejecutada. |
| CRUD ineficiente y concurrencia limitada | El `IndexFlatIP` conserva vectores y requiere mantener por separado su correspondencia con IDs y documentos. Actualizar o eliminar conocimiento exige coordinar índice, manifiesto y corpus; FAISS no aporta por sí solo una API documental completa ni gestión de concurrencia. | ChromaDB integra IDs, documentos y metadatos y ofrece `get`, `upsert`, `update` y `delete` dentro de una colección persistente. Esto simplifica el mantenimiento incremental y prepara el evento de negocio B.3. No se han probado escrituras concurrentes reales ni se presume coordinación automática entre servidores. |

FAISS sigue siendo útil como índice liviano y rápido para búsqueda vectorial pura. ChromaDB se eligió cuando el dominio requiere persistencia documental, metadatos, filtros y actualización incremental; las capacidades posteriores se evaluarán en los apartados correspondientes.
