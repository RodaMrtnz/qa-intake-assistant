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
`DOC-003` es cercano semánticamente, pero `activo=false` impide recomendarlo: esto anticipa el filtro obligatorio **`activo=true`**, implementado y demostrado en B.4.

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

En las tres consultas el documento esperado quedó primero, con scores top-1 de `0.801476`, `0.802261` y `0.799975`. Los resultados secundarios son semánticamente cercanos, pero no necesariamente aplicables. `DOC-003` apareció segundo en la tercera consulta pese a estar inactivo: no es un fallo de A.4, que realiza búsqueda semántica pura sin filtrar vigencia. El caso demuestra por qué B.4 filtra `activo=true` dentro de la consulta de ChromaDB, no mediante post-filtering de los vecinos ya recuperados.

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

`tags_regionales` se serializa mediante `json.dumps(tags, ensure_ascii=False)` porque es una lista auxiliar de sinónimos y jerga, no el filtro duro principal. `activo` no se convierte en texto: B.4 lo filtra mediante un booleano real. La ingesta rechaza colecciones con métrica, modelo, dimensión, schema o IDs adicionales incompatibles, solicitando una migración explícita; no las elimina silenciosamente.

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
| Sin filtrado híbrido nativo | FAISS devuelve vecinos por posición y similitud, pero no conoce `plataforma`, `activo`, `proyecto` o `modulo`. En A.4 apareció `DOC-003` pese a estar inactivo porque la búsqueda fue puramente semántica. | ChromaDB almacena metadatos junto con los documentos y permite aplicar un `where` nativo durante la consulta. Esto permite exigir `activo=true` y una plataforma determinada al recuperar resultados, como se implementó y demostró en B.4. |
| CRUD ineficiente y concurrencia limitada | El `IndexFlatIP` conserva vectores y requiere mantener por separado su correspondencia con IDs y documentos. Actualizar o eliminar conocimiento exige coordinar índice, manifiesto y corpus; FAISS no aporta por sí solo una API documental completa ni gestión de concurrencia. | ChromaDB integra IDs, documentos y metadatos y ofrece `get`, `upsert`, `update` y `delete` dentro de una colección persistente. Esto simplifica el mantenimiento incremental y prepara el evento de negocio B.3. No se han probado escrituras concurrentes reales ni se presume coordinación automática entre servidores. |

FAISS sigue siendo útil como índice liviano y rápido para búsqueda vectorial pura. ChromaDB se eligió cuando el dominio requiere persistencia documental, metadatos, filtros y actualización incremental; las capacidades posteriores se evaluarán en los apartados correspondientes.

### B.3 — Evento de negocio en caliente

`DOC-007` representa una solución conocida para promociones Android del proyecto ficticio `tienda_web`. Su metadato inicial era `activo=true`. Se simuló que la solución debía retirarse temporalmente de circulación mientras era revisada, sin eliminar el antecedente ni cambiar el estado histórico del defecto.

El subcomando `hot-event` aplicó `activo=false` mediante `collection.upsert` y recuperó inmediatamente el registro mediante `collection.get(ids=["DOC-007"], include=["documents", "metadatas"])`. El registro continuó existiendo y la colección mantuvo 15 documentos. Solo cambió el booleano `activo`: el documento y los demás metadatos permanecieron iguales.

| Momento | Operación | `activo` | Cantidad de documentos |
| --- | --- | --- | ---: |
| Antes del evento | `get` | `true` | 15 |
| Durante el evento | `upsert` + `get` | `false` | 15 |
| Después de restaurar | `upsert` + `get` | `true` | 15 |

#### Elección de la operación

`add` no corresponde porque `DOC-007` ya existe y podría rechazar el ID duplicado. `update` serviría solamente si se garantiza previamente que el ID existe. `upsert` permite insertar o actualizar y hace que el flujo pueda repetirse sin crear otro registro. En este evento el ID ya existía, pero se utilizó la misma operación segura que la ingesta. Varias llamadas `upsert` no constituyen una única transacción ni resuelven por sí mismas la concurrencia distribuida.

#### Restauración y consumo de embeddings

Para conservar `base_conocimiento.json` como fuente de verdad y no afectar las pruebas posteriores de B.4, el script restauró el documento original en un bloque `finally`, mediante otro `upsert`. El flujo contempla errores donde una escritura pudo haberse aplicado sin recibir confirmación: comprueba el estado y, ante un cambio o incertidumbre, intenta restaurar; si falla la restauración, informa el error original y el de restauración sin revelar credenciales.

La posterior ejecución independiente de `verify` confirmó 15 documentos y coincidencia completa con el corpus. No se modificó `base_conocimiento.json`. Tanto el cambio como la restauración incluyeron el documento en cada `upsert`, por lo que se generaron dos embeddings documentales mediante `RETRIEVAL_DOCUMENT`. La ejecución posterior de `verify` no generó embeddings ni llamó a Gemini.

#### Evidencia real

```text
> python .\vector_db.py hot-event
Evento en caliente sobre DOC-007.
Estado anterior: activo=true.
Operación aplicada: upsert.
Estado recuperado con get: activo=false.
Cantidad de documentos durante el evento: 15.
Cambio verificado: la solución quedó temporalmente fuera de vigencia.
Restauración aplicada mediante upsert.
Estado final: activo=true.
Colección restaurada y verificada contra base_conocimiento.json.
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

Ambas ejecuciones terminaron con código `0`. La prueba demuestra una actualización incremental de metadatos recuperable inmediatamente y su restauración, pero no constituye una prueba de concurrencia, bloqueo distribuido o transacción multirregistro. B.4–B.6 se documentan a continuación.

### B.4 — Búsqueda híbrida con filtros nativos

La función implementada es `buscar_defectos(query_semantica, plataforma, solo_activos, n_resultados, collection)`. La similitud semántica se obtiene mediante `query_texts`, que activa `GeminiEmbeddingFunction.embed_query` con `RETRIEVAL_QUERY`. Los embeddings documentales persistidos no se regeneran.

ChromaDB aplica los filtros durante la consulta mediante `where`, combinando la plataforma solicitada y `activo=true`:

```python
{
    "$and": [
        {"plataforma": {"$eq": plataforma}},
        {"activo": {"$eq": True}},
    ]
}
```

No existe postfiltrado en Python ni se piden resultados adicionales para filtrarlos o recortarlos después. La decisión de negocio es no recomendar conocimiento inactivo; por eso `solo_activos=False` se rechaza. La colección utiliza distancia coseno y el programa informa:

```python
similitud_coseno = 1.0 - distancia_coseno
```

Todavía no se aplica un umbral mínimo de similitud porque su elección corresponde a C.2. Los resultados pertenecen a un corpus académico sintético y no confirman tickets externos.

| Consulta | Plataforma exigida | Primer resultado | Similitud top-1 | Efecto del filtro |
| -------- | ------------------ | ---------------- | --------------: | ----------------- |
| Carrito/cesta | `android` | `DOC-001` | 0.801475 | Todos los resultados fueron Android y activos. |
| Login 401 | `web` | `DOC-002` | 0.802260 | Todos los resultados fueron web y activos. |
| Face ID después de actualizar iOS | `ios` | `DOC-009` | 0.625396 | `DOC-003` fue excluido por `activo=false`; solo dos registros iOS satisfacían ambos filtros. |

`DOC-003`, aunque es el antecedente semánticamente más directo del corpus para Face ID, tiene `activo=false` y fue excluido. Chroma devolvió solo dos documentos porque únicamente dos registros iOS satisfacían simultáneamente el filtro de plataforma y vigencia. `DOC-009` no se presenta como una solución suficientemente relevante: sin umbral, solamente es el vecino activo más cercano dentro del subconjunto permitido.

#### Evidencia real

```text
> python .\vector_db.py search --query "La app se cierra al abrir la cesta después de agregar un artículo agotado." --platform android --n-results 3
Corpus sintético: los resultados no confirman tickets externos.
Filtro nativo: {"$and": [{"plataforma": {"$eq": "android"}}, {"activo": {"$eq": true}}]}
1. ID=DOC-001 | defect_id=DEF-1001 | proyecto=tienda_web | plataforma=android | modulo=carrito | activo=True | distancia=0.198525 | similitud=0.801475
2. ID=DOC-007 | defect_id=DEF-1007 | proyecto=tienda_web | plataforma=android | modulo=promociones | activo=True | distancia=0.329208 | similitud=0.670792
3. ID=DOC-008 | defect_id=DEF-1008 | proyecto=portal_clientes | plataforma=android | modulo=autenticacion | activo=True | distancia=0.374876 | similitud=0.625124
Código de salida: 0
```

```text
> python .\vector_db.py search --query "El login devuelve 401 después de renovar una sesión vencida." --platform web --n-results 3
Corpus sintético: los resultados no confirman tickets externos.
Filtro nativo: {"$and": [{"plataforma": {"$eq": "web"}}, {"activo": {"$eq": true}}]}
1. ID=DOC-002 | defect_id=DEF-1002 | proyecto=portal_clientes | plataforma=web | modulo=autenticacion | activo=True | distancia=0.197740 | similitud=0.802260
2. ID=DOC-012 | defect_id=DEF-1012 | proyecto=banca_movil | plataforma=web | modulo=reportes | activo=True | distancia=0.436141 | similitud=0.563859
3. ID=DOC-010 | defect_id=DEF-1010 | proyecto=portal_clientes | plataforma=web | modulo=adjuntos | activo=True | distancia=0.441705 | similitud=0.558295
Código de salida: 0
```

```text
> python .\vector_db.py search --query "Después de actualizar iOS, Face ID rechaza el acceso y hay que registrar nuevamente la biometría." --platform ios --n-results 3
Corpus sintético: los resultados no confirman tickets externos.
Filtro nativo: {"$and": [{"plataforma": {"$eq": "ios"}}, {"activo": {"$eq": true}}]}
1. ID=DOC-009 | defect_id=DEF-1009 | proyecto=portal_clientes | plataforma=ios | modulo=autenticacion | activo=True | distancia=0.374604 | similitud=0.625396
2. ID=DOC-006 | defect_id=DEF-1006 | proyecto=tienda_web | plataforma=ios | modulo=notificaciones | activo=True | distancia=0.426696 | similitud=0.573304
Código de salida: 0
```

Las tres ejecuciones terminaron con código `0`. La prueba demuestra búsqueda semántica combinada con filtrado nativo por metadatos y que un antecedente inactivo queda excluido antes de formar los resultados. No demuestra todavía un umbral de aceptación, calidad universal de recuperación, ETL, purga ni Killer Queries. El ETL y la purga se documentan en B.5; las Killer Queries, en B.6.

### B.5 — ETL y purga semántica

#### Dataset de prueba controlado

`base_conocimiento.json` permanece como fuente de verdad limpia con 15 documentos. Para no corromper el corpus utilizado en A.3–B.4, se creó `base_conocimiento_etl_sucia.json`: contiene 18 registros, compuestos por los 15 documentos conceptuales originales, dos inconsistencias estructurales y tres paráfrasis casi duplicadas. No contiene tickets externos ni datos internos reales.

#### Extracción y normalización

El ETL extrae el JSON en UTF-8 y aplica estas dos correcciones reales; las posiciones se cuentan desde cero:

| Posición | Documento | Inconsistencia | Normalización |
| -------: | --------- | -------------- | ------------- |
| 9 | `DOC-010` | clave `platform` | se renombró a `plataforma` |
| 11 | `DOC-012` | `activo` almacenado como string `"true"` | se convirtió al booleano real `true` |

El archivo sucio no fue sobrescrito. Después de normalizar, el ETL valida estructura, claves, plataformas, booleanos y campos obligatorios. Los strings booleanos no reconocidos se rechazan en lugar de convertirse silenciosamente.

#### Colisión de IDs

La paráfrasis del carrito reutilizaba deliberadamente `DOC-001`. El algoritmo conservó la primera aparición canónica, reasignó determinísticamente la segunda a `DOC-DUP-001`, registró la colisión y dejó todos los IDs únicos antes de vectorizar. El mecanismo es general: busca un identificador libre y agrega un sufijo determinístico si el reemplazo ya está ocupado; no utiliza un `if` exclusivo para `DOC-001`.

#### Embeddings y criterio de comparación

Se utilizó `gemini-embedding-001`, dimensión 768 y tarea `RETRIEVAL_DOCUMENT` para los 18 textos normalizados. Los vectores se convirtieron a `float32`, se validaron en cantidad, dimensión, valores finitos y ausencia de vectores nulos, y se normalizaron antes de comparar. No se persistieron embeddings ni se crearon índices FAISS o bases ChromaDB.

```python
distancia_coseno = 1.0 - similitud_coseno
```

Un par solamente puede purgarse si cumple simultáneamente distancia coseno menor o igual al umbral, mismo proyecto, misma plataforma y mismo módulo. Esto evita eliminar documentos por compartir vocabulario general pero pertenecer a contextos distintos. Se priorizan los IDs canónicos `DOC-001` a `DOC-015`; si esa regla no alcanza, se conserva el primero según el orden normalizado. Cada eliminación se compara directamente con el documento conservado y registra ambos IDs, scores, contexto y motivo.

#### Umbral justificado

El umbral adoptado para esta prueba fue:

```text
distancia coseno <= 0.15
```

equivalente a:

```text
similitud coseno >= 0.85
```

Las tres paráfrasis preparadas quedaron muy por debajo del límite, con distancias entre `0.042900` y `0.048730` y similitudes entre `0.951270` y `0.957100`. Ningún otro par que cumpliera las condiciones de proyecto, plataforma y módulo quedó dentro del umbral. Se eliminaron exactamente los tres duplicados previstos y el corpus resultante coincidió completamente con los 15 documentos de `base_conocimiento.json`.

El umbral fue validado sobre este corpus académico controlado; no garantiza rendimiento universal y debería recalibrarse con datos reales más variados antes de producción. La salida literal conserva la denominación «Umbral preliminar» del script.

#### Resultado de la purga

| ID conservado | ID eliminado | Similitud coseno | Distancia coseno | Proyecto | Plataforma | Módulo |
| ------------- | ------------ | ---------------: | ---------------: | -------- | ---------- | ------ |
| `DOC-001` | `DOC-DUP-001` | 0.951270 | 0.048730 | `tienda_web` | `android` | `carrito` |
| `DOC-002` | `DOC-DUP-002` | 0.957100 | 0.042900 | `portal_clientes` | `web` | `autenticacion` |
| `DOC-015` | `DOC-DUP-015` | 0.954292 | 0.045708 | `gestion_interna` | `desktop` | `formularios` |

Se pasó de 18 documentos iniciales a 15 finales, con dos correcciones estructurales, una colisión de ID resuelta y tres duplicados semánticos eliminados. La comparación estricta en memoria confirmó los mismos 15 IDs, documentos y metadatos que la fuente limpia, sin depender del formato o indentación del JSON. No se sobrescribió `base_conocimiento.json` ni se generó un archivo limpio duplicado.

#### Por qué `SELECT DISTINCT` no alcanza

`SELECT DISTINCT` elimina filas con valores iguales. Tras resolver la colisión, las paráfrasis tenían IDs y textos diferentes y utilizaban sinónimos como `carrito/cesta`, `producto/artículo` o formulaciones distintas para una sesión vencida. Aunque representaban el mismo incidente, no eran duplicados textuales: fue necesario comparar significado mediante embeddings y distancia coseno.

#### Evidencia real

```text
> python .\etl_purga.py --threshold 0.15
Datos académicos sintéticos; no son tickets externos.
Documentos extraídos: 18
Correcciones estructurales: 2
{"posicion": 9, "id": "DOC-010", "correccion": "platform -> plataforma"}
{"posicion": 11, "id": "DOC-012", "correccion": "activo: string -> bool"}
Colisiones resueltas: 1
{"id_original": "DOC-001", "id_nuevo": "DOC-DUP-001", "motivo": "ID repetido; se conserva la primera aparición"}
Modelo: gemini-embedding-001; dimensión: 768
Umbral preliminar: distancia <= 0.15; similitud >= 0.85
{"id_conservado": "DOC-001", "id_eliminado": "DOC-DUP-001", "similitud_coseno": 0.951269805431366, "distancia_coseno": 0.04873019456863403, "proyecto": "tienda_web", "plataforma": "android", "modulo": "carrito", "motivo": "Distancia dentro del umbral y mismo proyecto/plataforma/módulo; prioridad canónica"}
{"id_conservado": "DOC-002", "id_eliminado": "DOC-DUP-002", "similitud_coseno": 0.9571004509925842, "distancia_coseno": 0.04289954900741577, "proyecto": "portal_clientes", "plataforma": "web", "modulo": "autenticacion", "motivo": "Distancia dentro del umbral y mismo proyecto/plataforma/módulo; prioridad canónica"}
{"id_conservado": "DOC-015", "id_eliminado": "DOC-DUP-015", "similitud_coseno": 0.9542924165725708, "distancia_coseno": 0.0457075834274292, "proyecto": "gestion_interna", "plataforma": "desktop", "modulo": "formularios", "motivo": "Distancia dentro del umbral y mismo proyecto/plataforma/módulo; prioridad canónica"}
Documentos finales: 15
El ETL reconstruyó la fuente limpia: coincidencia completa con base_conocimiento.json.
Código de salida: 0
```

PowerShell informó aparte `$LASTEXITCODE = 0`.

La prueba demuestra normalización, resolución de IDs y purga semántica sobre un conjunto controlado. No demuestra todavía ingestión automática desde sistemas externos ni calibración con un corpus productivo. Las Killer Queries se documentan en B.6.

### B.6 — Killer Queries

Se evaluaron tres consultas trampa sobre el corpus académico sintético: jerga para el cierre del carrito Android, Face ID después de actualizar iOS y una impresora 3D fuera del catálogo. Evalúan respectivamente recuperación por significado, riesgo de recomendar conocimiento obsoleto y aceptación indebida del vecino matemáticamente más cercano. Las tres pasaron.

| Caso | Resultado principal | Similitud coseno | ¿Pasó? |
| ---- | ------------------- | ---------------: | ------ |
| Jerga: changuito y mercadería sin existencias | `DOC-001` top-1 aceptado; vecinos Android activos | 0.773748 | Sí |
| Face ID: antecedente obsoleto | Crudo: `DOC-003` inactivo top-1; híbrido: excluido, `DOC-009` top-1 y `DOC-006` segundo; respuesta `No tengo esa información.` | Crudo: 0.784778; híbrido: 0.622149 y 0.570439 | Sí |
| Impresora 3D fuera del catálogo | Único vecino `DOC-015`, rechazado; respuesta `No tengo esa información.` | 0.537786 | Sí |

La evidencia detallada, vecinos, distancias y salida literal están en [resultados_killer_queries.md](resultados_killer_queries.md). Se utilizaron cuatro embeddings de consulta y cero documentales, sin escrituras sobre ChromaDB. El `where` productivo siguió siendo nativo por plataforma y `activo=true`; el diagnóstico sin filtros del segundo caso solo evidenció el riesgo y no produjo la respuesta productiva. No hubo postfiltrado manual de metadatos.

El umbral inclusivo de similitud `>= 0.70` aceptó el antecedente correcto y permitió abstenerse en los otros dos casos. Todavía se denomina preliminar hasta la justificación final de C.2; estas pruebas sobre un corpus pequeño no garantizan calidad universal. Los resultados no confirman tickets externos.

## Parte C — Coherencia e integración

### C.1 — Cadena de coherencia con la Entrega 1

La Entrega 1 documentó un sistema más amplio que su prototipo: el flujo B.6 y el cierre C.5 de `informe.md` distinguen la extracción implementada de las consultas y acciones futuras. La Entrega 2 incorpora recuperación vectorial sobre antecedentes académicos sintéticos; no convierte esos antecedentes en tickets corporativos ni implementa todas las fuentes previstas en el PEAS.

| Elemento de la Entrega 1 | Evidencia original | Implementación en la Entrega 2 | Alcance o limitación actual |
| ------------------------ | ------------------ | ------------------------------ | --------------------------- |
| Base de Conocimiento del PEAS | A.3 de `informe.md` proyecta SQL de defectos e interacciones, catálogos oficiales de productos, módulos, plataformas y versiones, reglas de severidad/prioridad, directorio de equipos y responsables, documentación funcional/técnica, historial de defectos y soluciones y una futura base vectorial para RAG. | Se implementó únicamente la porción vectorial: 15 antecedentes sintéticos en `base_conocimiento.json` como fuente de verdad, FAISS y ChromaDB persistentes, metadatos y vigencia, ETL y purga semántica sobre un dataset controlado. `proyecto` identifica escenarios ficticios, no un catálogo oficial. | No existen integraciones implementadas con SQL de negocio o Jira, reglas oficiales, directorio real ni documentación corporativa real. El almacenamiento interno de ChromaDB no equivale al esquema SQL de defectos e interacciones proyectado en B.5.3 de la Entrega 1. |
| `platform` / plataforma de la matriz | B.3 de `informe.md` incluye `platform` en las intenciones de reporte, búsqueda y orientación; `DefectExtraction` en `schemas.py` valida sus valores. | El corpus almacena `plataforma`; `buscar_defectos` la normaliza y envía el filtro nativo `plataforma=<valor>` en `where`. | No hay conversión automática desde la extracción. El contrato admite `other` y `null`, pero la búsqueda solo acepta `web`, `android`, `ios` y `desktop`; el futuro orquestador deberá pedir aclaración o abstenerse ante valores no admitidos, sin inventar una plataforma. |
| `module` | La matriz B.3 y el contrato Pydantic contemplan el módulo extraído por el LLM. | Se almacena como `modulo`; el ETL lo utiliza junto con proyecto y plataforma para limitar la comparación de duplicados. | Está disponible como metadato, pero `vector_db.py search` no lo utiliza como filtro obligatorio de recuperación. |
| `defect_id` | La matriz lo incluye para búsqueda y actualización. `schemas.py` normaliza a mayúsculas y valida el formato `DEF-` seguido de dígitos. | Se almacena como metadato sintético y se muestra en los resultados de búsqueda. | No se utiliza actualmente como filtro de búsqueda semántica. Validar su formato no confirma la existencia de un ticket externo ni autoriza su modificación. |
| `app_version` y `error_code` | B.3 incluye versión para reportes y código de error para reportes/búsquedas; ambos son campos opcionales del contrato. | Algunos documentos conservan referencias narrativas a versiones o actualizaciones y códigos, como el 401 de `DOC-002`. | No están modelados como metadatos duros independientes en ChromaDB. Las referencias genéricas a versiones no constituyen un catálogo de versiones exactas; Pydantic tampoco valida la existencia real de una versión o el significado de un código. |
| `summary`, `keywords`, pasos y resultados | La matriz y `DefectExtraction` incluyen `summary`, `keywords`, `steps_to_reproduce`, `expected_result` y `actual_result` según la intención. | `descripcion_semantica` contiene contexto, reproducción, resultados y solución; puede contrastarse con el contenido semántico de un reporte mediante embeddings. | No existe un constructor automático de `query_semantica` a partir de estos campos. `keywords` no se convierte automáticamente en `tags_regionales`, que es información auxiliar del corpus. |
| Intención, cambios solicitados y faltantes | B.3 define cinco intenciones; `requested_changes` describe actualizaciones solicitadas y `missing_fields` registra información faltante. El flujo B.6 reserva decisiones y acciones al backend. | La búsqueda y sus pruebas son herramientas separadas de solo lectura; no ejecutan las acciones de la matriz. | Falta el despacho integrado por intención y la gestión de aclaraciones. No se implementaron permisos, escritura de tickets ni ejecución de `requested_changes`. |
| Vigencia `activo` | El PEAS proyecta historial y fuentes confiables; `activo` no es un campo extraído por el contrato de la Entrega 1. | Es un booleano de vigencia de la Base de Conocimiento, establecido en el corpus y aplicado obligatoriamente mediante `activo=true`; `solo_activos=False` se rechaza. | No es una afirmación inventada por el LLM ni equivale al estado del defecto. Un antecedente resuelto puede seguir vigente; uno inactivo no debe recomendarse. |
| Parámetros extraídos desde `free_text` | `app.py` recibe texto por terminal o mediante `analyze_report`, lo envía a Gemini con el System Prompt y valida el JSON con `DefectExtraction.model_validate_json`. B.6 y C.5 de `informe.md` describen ese alcance. | Existen tanto la capa de interpretación/validación como la de recuperación: la plataforma validada puede convertirse en `plataforma`, y el contenido del reporte en `query_semantica`, para recuperar antecedentes activos. | Las dos capas todavía no están conectadas automáticamente en un único flujo. El endpoint web documentado en la Entrega 1 no está implementado por `app.py`; tampoco existe una generación de respuesta RAG integrada. |

Recorrido previsto, con las conexiones entre extracción y búsqueda todavía pendientes:

```text
free_text → Gemini con System Prompt → DefectExtraction validado por Pydantic → construcción de query_semantica y where → ChromaDB con plataforma y activo=true → candidatos aceptados por umbral
```

La validación asegura el contrato, no la verdad de todos los datos extraídos. El backend futuro deberá controlar los filtros y la abstención; este flujo no presenta una generación de respuesta final como componente ya implementado.

### C.2 — Umbral de aceptación

Se adopta para este corpus académico de 15 documentos el threshold inclusivo:

```text
similitud coseno >= 0.70
```

La evidencia siguiente conserva los valores exactos y distingue ejecuciones. Las decisiones de A.4/B.4 indican qué correspondería al aplicar este criterio a los scores documentados; esos scripts no aplicaron allí el umbral de aceptación.

| Evidencia | Similitud | Decisión |
| --------- | --------: | -------- |
| Carrito Android, A.4 (FAISS), `DOC-001` | 0.801476 | aceptar con el criterio adoptado |
| Carrito Android, B.4 (ChromaDB), `DOC-001` | 0.801475 | aceptar con el criterio adoptado |
| Login 401, A.4 (FAISS), `DOC-002` | 0.802261 | aceptar con el criterio adoptado |
| Login 401, B.4 (ChromaDB), `DOC-002` | 0.802260 | aceptar con el criterio adoptado |
| Botón Guardar, A.4 (FAISS), `DOC-015` | 0.799975 | aceptar con el criterio adoptado |
| Jerga `changuito/mercadería`, B.6, `DOC-001` | 0.773748 | aceptado efectivamente |
| Mejor vecino activo para Face ID, B.6, `DOC-009` | 0.622149 | rechazado efectivamente; abstención |
| Fuera del catálogo, B.6, `DOC-015` | 0.537786 | rechazado efectivamente; abstención |

Las pequeñas diferencias entre FAISS y ChromaDB corresponden a los resultados registrados y no se unifican como una sola medición. La consulta Face ID de B.4 fue distinta y obtuvo `0.625396` para `DOC-009`; también queda bajo 0.70, pero no debe confundirse con el `0.622149` de B.6. `DOC-009` es un vecino activo de recuperación de contraseña, no una solución validada para Face ID. El score crudo `0.784778` de `DOC-003` en B.6 tampoco habilita recomendarlo: `activo=false` lo excluye antes de la aceptación numérica.

ChromaDB puede devolver algún vecino cuando el subconjunto permitido contiene documentos, incluso si ninguno responde a la consulta; un filtro también puede dejar el conjunto vacío. Ser el vecino más cercano no significa ser una respuesta válida. Si ningún resultado alcanza 0.70, la respuesta controlada es exactamente:

```text
No tengo esa información.
```

Forzar el vecino más cercano por debajo del umbral sería una recomendación sin respaldo y puede inducir una alucinación. El criterio separó el antecedente correcto expresado con jerga de las alternativas activas para Face ID y del caso fuera de catálogo. Es adecuado como decisión para este conjunto controlado, no como garantía universal: antes de producción debe recalibrarse con más datos, consultas reales, positivos y negativos etiquetados y análisis de falsos positivos y falsos negativos. Un threshold alto puede omitir antecedentes útiles; uno bajo puede aceptar coincidencias irrelevantes.

Los dos umbrales resuelven problemas diferentes: **0.70 de similitud** acepta candidatos de búsqueda; **0.15 de distancia**, equivalente a **0.85 de similitud**, identifica casi duplicados únicamente en el ETL. B.5 eliminó las tres paráfrasis con similitudes `0.951270`, `0.957100` y `0.954292`, conservando íntegramente la fuente limpia; ese criterio de purga no reemplaza al umbral de recuperación.

`killer_queries.py` ya aplica realmente 0.70 mediante `aplicar_umbral` y produjo la abstención documentada. `vector_db.py search` muestra vecinos y scores como herramienta de inspección de B.4, pero no aplica por sí solo este threshold ni presenta una respuesta final al usuario. El umbral tampoco está integrado en `app.py`; las referencias previas a «preliminar» describen las etapas anteriores a esta adopción para el corpus académico.

### C.3 — Cierre: dónde se conecta

La búsqueda híbrida devuelve estructuras de Python con documentos, metadatos, distancia y similitud; falta un orquestador RAG que conecte `DefectExtraction` con esa recuperación.
Deberá construir la consulta y el `where`, aplicar el umbral y entregar solamente antecedentes aceptados al modelo generador para producir una respuesta trazable al usuario.
LangChain puede utilizarse en una unidad futura, pero no está implementado actualmente ni forma parte de las dependencias declaradas.
El LLM no debe consultar ni modificar directamente la base ni presentar como oficial un dato no recuperado; el backend deberá controlar esas operaciones.
