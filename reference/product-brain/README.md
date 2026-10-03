# Product Brain por dentro: plantillas, completitud y prompts

Referencia local para no volver a buscarlo. Todo lo que sigue se leyó del código fuente de Product Brain,
no de capturas ni de inferencias.

| | |
|---|---|
| Repo | `josefigueredo/acme-agent` (privado; backend en `acme-gpt-back/api/src/`) |
| Commit leído | `9b19a89bdb41345c0caf46b9c0b5a87eb924953a` (main, 2026-09-29) |
| Fecha de lectura | 2026-10-02 |
| Copia local | `upstream/` (gitignored: es código interno de otra área y no va al historial de WayOfWork) |
| Refrescar | `./refresh.sh` (o `./refresh.sh <ref>`) y comparar el commit con este README |

## Cómo se encontró (para repetirlo)

```bash
gh org list --limit 200                              # orgs visibles
gh search repos "acme-agent" --limit 20              # la URL de PB es backend-acme-agent-production…
gh search code "systemPrompt" --repo josefigueredo/acme-agent
gh repo clone josefigueredo/acme-agent /tmp/pb -- --depth 1 && rg -n "completionPercentage" /tmp/pb
```

- `gh search code` está limitado a unas 10 consultas por minuto. Para explorar, conviene clonar con `--depth 1` y usar `rg`.
- Las frases que muestra el chat ("Siguiente sección…") son salida del modelo, no aparecen en el código.
  Buscá nombres de constantes (`PRD_TEMPLATE_CONTENT`, `completionPercentage`, `PRD_PROMPT`).

## Mapa de archivos

| Archivo (`upstream/`) | Ruta original | Qué tiene |
|---|---|---|
| `base-templates.ts` | `db/base-templates.ts` | Plantillas: PRD (l. 11), ejemplo PRD (l. 181), RFC (l. 364), ejemplo RFC (l. 526), schema EPIC (l. 725), Caso de Negocio (l. 1017), tipos base (l. 1363) |
| `completion.ts` | `modules/documents/completion.ts` | Cálculo del %: `evaluateFieldState` (l. 72), `evaluateGroupState` (l. 184), `computeCompletion` (l. 220) |
| `open-questions-validation.ts` | `modules/documents/pipeline/open-questions-validation.ts` | Regla de preguntas abiertas (l. 22) |
| `field-groups.ts` | `modules/documents/pipeline/field-groups.ts` | Cómo se colapsan los placeholders numerados en tablas |
| `detector.ts` | `modules/documents/pipeline/detector.ts` | Extracción de campos: `{{campo}}` y también `{campo}`, únicos y en orden, incluidos los de los encabezados |
| `document-completion-guard.ts` | `modules/chat/document-completion-guard.ts` | El backend corrige al LLM cuando declara otro % (l. 169, l. 286) |
| `agent-prompts.config.ts` | `modules/agents/agent-prompts.config.ts` | `SHARED_PREAMBLE` (l. 11), `PRD_PROMPT` (l. 172), `RFC_PROMPT` (l. 251), `EPIC_PROMPT` (l. 473), `CASO_PROMPT` (l. 632) |

## Cómo se calcula el porcentaje

Lo calcula el **backend**, de forma determinista; Gemini no lo decide. El prompt le prohíbe calcularlo (`SHARED_PREAMBLE`,
regla 9) y el guard reemplaza cualquier % que el modelo declare por el real. En el chat aparece como
`**Completitud del documento:** N% · Pendiente: …`.

1. **Campos esperados:** los `{{placeholders}}` de la plantilla markdown (PRD, RFC) o las propiedades del schema JSON (EPIC).
2. **Estado de cada campo** (`evaluateFieldState`):
   - vacío: texto vacío o un `{{placeholder}}` sin reemplazar;
   - parcial: texto real que todavía contiene un `{{placeholder}}`;
   - lleno: **cualquier otro texto no vacío**, incluidos `[SIN DEFINIR] …`, `No aplica: …` y `Ninguna`.
3. **Tablas y listas numeradas** (`kpi_1_*`, `kpi_2_*`, …) se colapsan en **una unidad**: llena si al menos una fila
   tiene todas sus columnas, parcial si hay contenido suelto y vacía si no hay nada.
4. **`open_questions` es estricta:** **cada** fila necesita pregunta, owner y estado. Si una fila tiene solo la pregunta,
   el campo queda parcial. Por esto el modelo inventa owners.
5. **% = (llenos + 0,5 × parciales) / campos esperados.** El documento está completo con 100% y sin campos vacíos ni parciales.
6. **EPIC:** el schema tiene `required: []`, así que se cuentan **todas** las propiedades salvo las marcadas como
   `x-completion: optional` (hoy solo `end_date_actual`).

**Consecuencia:** se llega al 100% sin inventar nada si cada campo lleva la verdad o un marcador explícito. El 100% mide
estructura, no veracidad; por eso sigue haciendo falta `wow pbchat audit`.

## Por qué inventa (el origen de cada invento)

| Invento visto | Origen en el código |
|---|---|
| Marketplace con comprador y vendedor | El PRD tiene filas "Experiencia comprador" y "Operacion vendedor", y usuarios `buyer_*`, `seller_*` y `ops_*`. El ejemplo (`PRD_EXAMPLE_DATA`) es un marketplace |
| API Gateway | El RFC tiene una sección fija `### API Gateway` (tecnología, funcionalidad, configuración) |
| SLA | El RFC tiene una sección fija `### SLA` |
| Circuit breaker | El checklist del RFC pregunta "¿Se detallan mecanismos de resiliencia (circuit breaker, rate limit)?" |
| Owners en preguntas abiertas | `open_questions` exige owner en cada fila para contar como completa |
| North Star con targets y plazos | La tabla de KPIs tiene columnas Baseline, Target y Plazo; el prompt pide "baseline y target" |

## Comportamiento de los agentes que importa

- **Documentos compartidos** (`SHARED_PREAMBLE`, "CUANDO EL USUARIO COMPARTE…"): los analiza y **completa los campos en la
  misma respuesta**.
- **Regla anti-resumen:** el agente tiene prohibido resumir lo que le das. Más contenido termina siendo más contenido en el documento.
- **PRD Agent:**
  - Fase 1 de Discovery sin completar campos; Fase 2 de redacción; Fase 3 de checklist obligatorio.
  - Esa regla de la Fase 1 choca con la de "documento compartido". En el chat de IRIS ganó la de documento compartido: pegar el RFC-005 dio 60% de una.
  - Si insiste con Discovery, respondé "dale" a su resumen.
- **RFC Agent (EM Agent):**
  - Pide 3–4 rondas de preguntas antes de redactar.
  - **No redacta sin** stack, autenticación, arquitectura de alto nivel, despliegue, volumen esperado y rollout.
  - **Prioriza el código indexado** ("Código indexado > RFC/PRD previo > inferencia"): corrige los contratos contra los repos.
  - Usa `[TBD - verificar en código/Swagger]` para lo que no puede verificar.
- **Checklists de la Fase 3:**
  - PRD (l. 235): problema con datos, usuarios con jobs-to-be-done, North Star con baseline y target, KPIs con plazo,
    MVP acotado, out-of-scope explícito, requerimientos claros, riesgos clasificados, dependencias, happy path más edge cases.
  - RFC (l. 440): problema y glosario, impacto con números, objetivos con plazo, non-goals, diagrama completo, APIs
    verificadas, modelo de datos con tipos e índices, rollout con flags y fases, rollback concreto, resiliencia, riesgos,
    alternativas con pros y contras, preguntas abiertas, "¿un desarrollador puede codear sin preguntar?".
  - El checklist lo marca el modelo, no el backend: un ✅ no es evidencia.

## Plantillas, campo por campo

### PRD
- Metadata (`author`, `vertical`, `quarter_year`, `initiative_type`, `priority`, `prd_status`).
- Resumen Ejecutivo (`executive_summary`, `why_now`, `expected_outcome`).
- Vision y Estrategia (`roadmap_period`, `roadmap_alignment`, Valor de Negocio en 6 dimensiones, `vision_q2_plus`).
- Contexto, Problema y Oportunidad.
- Usuarios Target (3 bloques de 4 filas).
- Objetivo y Metricas de Exito: `objective` más tres tablas, KPIs primarios (métrica, baseline, target, plazo), secundarios y de salud.
- Alcance y Limitaciones: in-scope, out-of-scope, riesgos y supuestos.
- Requerimientos Clave (`key_requirements`) y Requerimientos No Funcionales.
- Dependencias Criticas (equipo, referente, necesidad, estado).
- Preguntas Abiertas.

### RFC
- Metadatos (`status`, `authors`, `version`, `target_date`, `prd_link`) y Resumen Ejecutivo.
- 1 Contexto y Alcance: problema, glosario, impacto, goals y non-goals.
- 2 Diseño: diagrama, componentes, repositorios, **API Gateway**, **Coexistencia y Fallback**, APIs A/B/C con endpoint,
  descripción, request y response, y modelo de datos más SQL.
- 3 Plan: hitos, rollout, rollback, riesgos y dependencias.
- 4 Transversales: seguridad, calidad, escalabilidad, **SLA** y resiliencia y observabilidad.
- 5 Alternativas.
- 6 Preguntas Abiertas.

### EPIC (JSON)
- **Campos de la épica:** `epic_name`, `objective`, `problem`, `strategic_objective`, `insights[]`, `expected_impact`,
  `assumptions[]`, `out_of_scope`, `dependencies[]`, `start_date`, `end_date_estimated`, `quarter`,
  `criticality` (Alta/Media/Baja), `priority`, `big_move`, `owner`, `status`, `related_documents[]`, `vertical`,
  `technical_context`, `components[]`, `labels[]`, `estimation_method`, `jira_prefix`, `notes`.
- **`user_stories[]`:** `id`, `title` (con prefijo `[BE]`/`[FE]`/`[BO]`), `user_story_text` ("Como… quiero… para…"),
  `context_and_need`, `assumptions[]`, `scope`, `out_of_scope`, `business_rules[]`, `edge_cases[]`, `assets[]`,
  `technical_info`, `acceptance_criteria[]` (**Gherkin**: Dado… Cuando… Entonces…), `definition_of_ready[]`,
  `definition_of_done[]`, más tasks.
- **Impacto en WayOfWork:** el paquete por épica de `wow pack` debería emitir esta forma, con los criterios en Gherkin
  y conservando el ancla `AC1` dentro del texto.

## Prompts derivados (en este repo)

- `skills/wow-pack/references/brownfield-prd.md`: PRD de un sistema existente, alineado campo por campo.
- `skills/wow-pack/references/brownfield-rfc.md`: RFC de un sistema existente, alineado campo por campo.

Si `refresh.sh` trae un commit distinto, compará `upstream/base-templates.ts` con las plantillas copiadas en esos prompts
y actualizalos antes de usarlos.

## Implementado en WayOfWork (Plan 5, `docs/superpowers/plans/2026-10-02-wow-pb-alignment.md`)

- **Plantillas copiadas** en `wow/templates/pb-prd.md` y `pb-rfc.md`; un test verifica que siguen iguales a `upstream/`.
- **`wow pack prd|rfc|epic`** renderiza con la forma de PB y deja `{{campo}}` donde falta el dato. El paquete de épica
  usa los campos del schema EPIC con etiquetas `Etiqueta (campo)`.
- **`wow pack check`** porta `completion.ts`, `open-questions-validation.ts` y la detección de grupos para predecir el %.
  En la épica valida enums, fechas, Fibonacci, Gherkin, DoR y DoD.
- **Modo `greenfield|brownfield`** en el manifiesto. En brownfield, la guía pide `/spec-kit.discovery`, que escribe en
  **`.spec-kit/discovery/architecture.md`** (verificado en `scripts/bash/spec-kit-discovery-orchestrator.sh`).
- **La auditoría** ignora encabezados y cláusulas negadas, y suma "circuit breaker" y "Kong" a la lista semilla.
- **Paquetes de registro (2026-10-03, después del piloto PLATE-491):** `wow pack prd|rfc` sale por defecto con todo
  campo lleno: contenido real donde el plan orienta (Goal, Problem, Contexto, Constraints, Non-goals, Decisions,
  done_when, componentes) y `No aplica: …` en el resto, porque el backend cuenta ese texto como lleno. `--full` (deprecado)
  conserva el modo con `{{campo}}`. `wow pack check` también falla con lo que PB rompe o filtra a Jira en el piloto:
  ids C14/D2, sufijos "(tarea x.y)", ítems de lista con comas (PB los parte) y bloques de API más allá de A–C.
- **Límite conocido:** la predicción lee el paquete alineado por secciones; PB lo mapea con Gemini. Si Gemini mapea
  distinto puede haber diferencias chicas, y la cifra autoritativa sigue siendo `**Completitud del documento:** N%`.
