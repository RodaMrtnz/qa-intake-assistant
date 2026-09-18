# Resultados de Killer Queries

Fecha de ejecución: **2026-09-18**, fecha local comprobada en el sistema. Modelo de embeddings: `gemini-embedding-001`; dimensión: 768; métrica: distancia coseno. Umbral preliminar de aceptación: similitud `>= 0.70`.

Se utilizó un corpus académico sintético de 15 documentos. La ejecución generó cuatro embeddings de consulta y cero embeddings documentales, sin ninguna escritura sobre ChromaDB. Los resultados no confirman tickets externos.

| # | Consulta | Qué pone a prueba | Resultado esperado | Resultado real | ¿Pasó? |
| - | -------- | ----------------- | ------------------ | -------------- | ------ |
| 1 | Cuando mando al changuito una mercadería que ya no tiene existencias, la app se baja sola al querer revisar la compra. | Poder semántico con jerga: changuito, mercadería, sin existencias y se baja sola, sin repetir los términos principales del documento. | `DOC-001` top-1, similitud >= 0.70 y solo documentos Android activos. | `DOC-001` top-1: similitud `0.773748`, distancia `0.226252`; aceptado. Todos los vecinos fueron Android y activos. | Sí |
| 2 | Después de actualizar iOS, Face ID rechaza siempre el desbloqueo y obliga a registrar nuevamente el acceso biométrico. | El metadato salva el día: impedir recomendar una solución obsoleta recuperada por la semántica cruda. | `DOC-003` predominante en diagnóstico; excluirlo por `activo=false`; abstenerse si ningún iOS activo alcanza 0.70. | Crudo: `DOC-003` top-1, inactivo, similitud `0.784778`, distancia `0.215222`. Híbrido: excluido; `DOC-009` (`0.622149`) y `DOC-006` (`0.570439`) no alcanzaron el umbral. Respuesta: `No tengo esa información.` | Sí |
| 3 | La impresora 3D industrial quema el filamento al calibrar la temperatura del extrusor. | Fuera del catálogo: evitar aceptar automáticamente al vecino matemáticamente más cercano. | Ningún Desktop activo alcanza 0.70; responder `No tengo esa información.` | Único vecino: `DOC-015`, similitud `0.537786`, distancia `0.462214`; no aceptado. Respuesta: `No tengo esa información.` | Sí |

## Caso 1 — Poder semántico con jerga

Consulta: «Cuando mando al changuito una mercadería que ya no tiene existencias, la app se baja sola al querer revisar la compra.»

Filtro nativo: `plataforma=android` y `activo=true`, combinados mediante `$and` en `where`.

| Vecino | Distancia coseno | Similitud coseno |
| ------ | --------------: | ---------------: |
| `DOC-001` | 0.226252 | 0.773748 |
| `DOC-007` | 0.323134 | 0.676866 |
| `DOC-008` | 0.387532 | 0.612468 |

Todos los vecinos recibidos fueron Android y activos. Resultado funcional: `DOC-001` fue el único antecedente sintético aceptado. El caso pasó porque fue top-1 y alcanzó el umbral usando jerga distinta de los términos principales del documento.

## Caso 2 — El metadato salva el día

Consulta: «Después de actualizar iOS, Face ID rechaza siempre el desbloqueo y obliga a registrar nuevamente el acceso biométrico.»

### Diagnóstico semántico crudo sin `where`

| Vecino | Plataforma | Activo | Distancia coseno | Similitud coseno |
| ------ | ---------- | ------ | --------------: | ---------------: |
| `DOC-003` | ios | false | 0.215222 | 0.784778 |
| `DOC-009` | ios | true | 0.377851 | 0.622149 |
| `DOC-008` | android | true | 0.392811 | 0.607189 |

`DOC-003` apareció en posición 1 con score alto, pero su conocimiento está inactivo. El diagnóstico sin filtros se utilizó únicamente para evidenciar el riesgo; no produjo la respuesta del sistema.

### Búsqueda productiva con filtro nativo

```python
{
    "$and": [
        {"plataforma": {"$eq": "ios"}},
        {"activo": {"$eq": True}},
    ]
}
```

| Vecino | Distancia coseno | Similitud coseno |
| ------ | --------------: | ---------------: |
| `DOC-009` | 0.377851 | 0.622149 |
| `DOC-006` | 0.429561 | 0.570439 |

Ambos vecinos productivos fueron iOS y activos; `DOC-003` quedó excluido. La respuesta productiva provino de la consulta con `where`, sin postfiltrado manual de metadatos. Python aplicó únicamente el umbral numérico. Como ninguno alcanzó 0.70, el resultado funcional fue exactamente `No tengo esa información.` El caso pasó por la exclusión del antecedente obsoleto y la abstención.

## Caso 3 — Fuera del catálogo

Consulta: «La impresora 3D industrial quema el filamento al calibrar la temperatura del extrusor.»

Filtro nativo: `plataforma=desktop` y `activo=true`, combinados mediante `$and` en `where`.

| Vecino | Distancia coseno | Similitud coseno |
| ------ | --------------: | ---------------: |
| `DOC-015` | 0.462214 | 0.537786 |

El único vecino fue Desktop y activo, pero su similitud no alcanzó 0.70. No fue aceptado y el resultado funcional fue exactamente `No tengo esa información.` El caso pasó porque no se presentó el vecino más cercano como una solución válida para un tema ausente del corpus.

## Evidencia literal

```text
> python .\killer_queries.py
Corpus académico sintético; no confirma tickets externos.
Umbral preliminar de aceptación: 0.70

Caso 1 — Poder semántico con jerga
Consulta: Cuando mando al changuito una mercadería que ya no tiene existencias, la app se baja sola al querer revisar la compra.
Filtro productivo nativo: {"$and": [{"plataforma": {"$eq": "android"}}, {"activo": {"$eq": true}}]}
Vecinos productivos recibidos:
1. ID=DOC-001 | plataforma=android | activo=True | distancia=0.226252 | similitud=0.773748
2. ID=DOC-007 | plataforma=android | activo=True | distancia=0.323134 | similitud=0.676866
3. ID=DOC-008 | plataforma=android | activo=True | distancia=0.387532 | similitud=0.612468
Expectativa: DOC-001 top-1 con similitud >= 0.70; todos Android y activos.
Resultado funcional final:
Antecedentes sintéticos aceptados: DOC-001
PASÓ
Motivo: Se cumplieron todas las expectativas del caso.

Caso 2 — El metadato salva el día
Consulta: Después de actualizar iOS, Face ID rechaza siempre el desbloqueo y obliga a registrar nuevamente el acceso biométrico.
Diagnóstico semántico crudo, sin where; no es una búsqueda productiva.
Vecinos crudos (sin postfiltrado):
1. ID=DOC-003 | plataforma=ios | activo=False | distancia=0.215222 | similitud=0.784778
2. ID=DOC-009 | plataforma=ios | activo=True | distancia=0.377851 | similitud=0.622149
3. ID=DOC-008 | plataforma=android | activo=True | distancia=0.392811 | similitud=0.607189
DOC-003: posición=1; similitud=0.784778.
Filtro productivo nativo: {"$and": [{"plataforma": {"$eq": "ios"}}, {"activo": {"$eq": true}}]}
Vecinos productivos recibidos:
1. ID=DOC-009 | plataforma=ios | activo=True | distancia=0.377851 | similitud=0.622149
2. ID=DOC-006 | plataforma=ios | activo=True | distancia=0.429561 | similitud=0.570439
Expectativa: DOC-003 inactivo y predominante en diagnóstico; excluido del flujo iOS activo; sin resultados aceptados, abstención.
Resultado funcional final:
No tengo esa información.
PASÓ
Motivo: Se cumplieron todas las expectativas del caso.

Caso 3 — Fuera del catálogo
Consulta: La impresora 3D industrial quema el filamento al calibrar la temperatura del extrusor.
Filtro productivo nativo: {"$and": [{"plataforma": {"$eq": "desktop"}}, {"activo": {"$eq": true}}]}
Vecinos productivos recibidos:
1. ID=DOC-015 | plataforma=desktop | activo=True | distancia=0.462214 | similitud=0.537786
Expectativa: Ningún vecino alcanza 0.70; responder: No tengo esa información.
Resultado funcional final:
No tengo esa información.
PASÓ
Motivo: Se cumplieron todas las expectativas del caso.
Consultas completadas: 4; embeddings documentales generados: 0.
Código de salida: 0
```

PowerShell informó además `$LASTEXITCODE = 0`.

## Reflexión

El caso 1 muestra recuperación por significado, no por coincidencia literal. El caso 2 demuestra que un score alto no alcanza si el conocimiento está fuera de vigencia. El caso 3 muestra que existe un vecino matemático dentro del subconjunto consultado, pero no necesariamente una respuesta válida.

El umbral `0.70` funcionó en estas pruebas: aceptó el antecedente correcto con `0.773748`, rechazó alternativas filtradas de `0.622149` o menos y rechazó el fuera de catálogo con `0.537786`. Sigue siendo un umbral calibrado sobre un corpus académico pequeño, no una garantía universal; su justificación final corresponde a C.2.
