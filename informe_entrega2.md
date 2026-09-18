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
