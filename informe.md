# Parte A

## A.1 — El caso

QA Intake Assistant es una aplicación destinada a equipos de calidad de empresas que desarrollan software web y móvil. Actualmente, los reportes de defectos llegan como texto libre y deben ser revisados manualmente para identificar la intención del usuario, extraer datos técnicos y determinar qué acción corresponde. El sistema propuesto utiliza un LLM para convertir esos mensajes desestructurados en datos validados, mientras que las consultas y operaciones sobre información real quedan bajo el control del backend.

## A.2 — Evidencia de la necesidad

La prueba aportada fue realizada el 6 de septiembre de 2026 con ChatGPT, sin identificación específica del modelo en la interfaz. A continuación se transcriben el prompt utilizado y la respuesta completa obtenida.

### Prompt utilizado

Actuá como el sistema interno de gestión de defectos de una empresa que desarrolla aplicaciones web y móviles.

Un tester informa:

“Desde la última actualización, al iniciar sesión en la aplicación móvil con una cuenta existente aparece el error 401. El problema ocurre en Android y comenzó esta mañana.”

Indicá:

1. Si este defecto ya se encuentra registrado.
2. Su identificador dentro del sistema.
3. Su severidad oficial.
4. Su prioridad actual.
5. El desarrollador al que está asignado.
6. Su estado actual.

Respondé directamente como lo haría el sistema interno de la empresa.

### Respuesta completa del modelo

DEFECT MATCH RESULT

1. **Registrado:** Sí
2. **Identificador:** DEF-1847
3. **Severidad oficial:** Critical
4. **Prioridad actual:** P1 — High
5. **Asignado a:** Martín López — Backend Developer
6. **Estado actual:** In Progress

### Análisis de la alucinación

El modelo inventó todos los datos internos solicitados:

- No podía saber que el defecto ya estaba registrado.
- Inventó el identificador `DEF-1847`.
- No conocía las reglas oficiales para establecer severidad y prioridad, por lo que las etiquetas asignadas no tenían respaldo.
- Inventó al desarrollador Martín López y su rol de Backend Developer.
- No tenía acceso al estado actual del supuesto defecto.

Presentó esos datos con un nivel de confianza alto: no manifestó incertidumbre ni aclaró que no tenía acceso al sistema interno. El formato de la respuesta podía hacer que el usuario interpretara los datos inventados como información oficial.

Para responder correctamente, necesitaba acceso a una fuente de verdad, como una base SQL de defectos, Jira o una API del gestor de incidencias, además de la configuración de severidades y prioridades y el directorio real de integrantes. El LLM puede interpretar el reporte, pero no debe actuar como autoridad sobre datos internos. Las consultas y la aplicación de reglas de negocio deben quedar bajo control del backend.

## A.3 — PEAS extendido

La siguiente tabla describe el sistema propuesto. Las integraciones y capacidades mencionadas corresponden al diseño previsto; todavía no están implementadas.

| Pilar | Descripción |
| --- | --- |
| **Performance** | Exactitud en la clasificación de intenciones.<br>Porcentaje de reportes que superan la validación de Pydantic.<br>Exactitud en la extracción de plataforma, módulo, código de error y pasos de reproducción.<br>Reducción del tiempo necesario para registrar y clasificar un defecto.<br>Tasa de datos inventados o no respaldados por fuentes internas, cuyo valor objetivo debe ser cero.<br>Porcentaje de casos ambiguos correctamente derivados a revisión humana. |
| **Environment** | El sistema está previsto como una aplicación web utilizada por testers, QA Leads, soporte y otros participantes del proceso de calidad. En una versión completa se comunicará con un gestor de defectos como Jira, una base SQL, documentación del proyecto y servicios de autenticación. Deberá procesar reportes provenientes de aplicaciones web y móviles. |
| **Actuators** | Mostrar al usuario los datos extraídos y validados.<br>Solicitar información faltante.<br>Consultar defectos registrados.<br>Crear un borrador de defecto para revisión.<br>Derivar un reporte al equipo correspondiente.<br>Registrar la interacción y la respuesta del sistema.<br>En una versión futura, enviar notificaciones o generar reportes.<br>Las acciones de escritura sensibles deberán ser confirmadas y ejecutadas por el backend, no directamente por el LLM. |
| **Sensors** | Texto libre ingresado en un formulario web.<br>Plataforma afectada.<br>Versión de la aplicación.<br>Código o mensaje de error.<br>Pasos de reproducción.<br>Resultado esperado y resultado actual.<br>Archivos adjuntos o capturas en versiones futuras.<br>Respuestas obtenidas de SQL, Jira u otras APIs internas. |
| **Base de conocimiento** | Base SQL de defectos e interacciones.<br>Catálogo oficial de productos, módulos, plataformas y versiones.<br>Reglas internas de severidad y prioridad.<br>Directorio de equipos y responsables.<br>Documentación funcional y técnica.<br>Historial de defectos y soluciones.<br>En el futuro, una base vectorial para consultar documentos mediante RAG. |

## A.4 — Anatomía del token

Se comparan dos consultas equivalentes en español e inglés:

**Español:**

“Desde la última actualización, al iniciar sesión en la aplicación móvil con una cuenta existente aparece el error 401. El problema ocurre en Android y comenzó esta mañana.”

**Inglés:**

“Since the latest update, logging into the mobile application with an existing account returns a 401 error. The issue occurs on Android and started this morning.”

El archivo `token_analysis.py` utiliza `tiktoken.encoding_for_model("gpt-4o")` para contar los tokens del texto de cada consulta, sin incluir las comillas tipográficas que las delimitan en este informe. El análisis se ejecuta localmente, sin llamadas a la API de OpenAI ni credenciales.

Resultados obtenidos al ejecutar `.\.venv\Scripts\python.exe token_analysis.py` en el entorno del proyecto con tiktoken 0.14.0:

| Consulta | Cantidad de tokens |
| --- | ---: |
| Español | 32 |
| Inglés | 30 |

La consulta en español utilizó 2 tokens más que la consulta en inglés.

Una diferencia pequeña por consulta puede volverse significativa al procesar miles de reportes diarios.
El costo total no depende solo del texto del usuario, sino también del System Prompt, los ejemplos, el contexto recuperado y la salida generada.

# Parte B

## Subsecciones por definir según la consigna

# Parte C

## Subsecciones por definir según la consigna
