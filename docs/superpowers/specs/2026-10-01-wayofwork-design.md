# WayOfWork — diseño

Fecha: 2026-10-01
Estado: diseño acordado en conversación, sección por sección. Pendiente de revisión del spec escrito.
Autor: José Figueredo, con Claude.

## 1. Por qué

El workflow de entrega con Product Brain (PB) + Spec-Kit + modelos fuertes (Claude, Codex) hoy vive en dos HTML
(`SPECKIT/docs/site/index.html` y `way-of-work.html`) y en la cabeza del operador. Tres problemas concretos:

- **No hay quién diga "qué sigue y dónde".** Cada paso ocurre en una herramienta distinta (harness propio, PB, Cursor) con un modelo
  distinto, y el orden y los criterios de salida hay que recordarlos.
- **El trabajo en Claude y Codex no se ve.** La telemetría de Spec-Kit (New Relic) solo registra los comandos `/spec-kit.*` y, en
  Cursor interactivo, modelo y tokens. Lo que se hace en cuentas propias queda invisible para la organización.
- **El harness `ic` creció hasta ser el problema.** La v1 tiene un `SKILL.md` de 1633 líneas y ~700 asserts sobre prosa; la v2
  (planeada, sin empezar) lo reduce pero sigue siendo una skill monolítica con su propio kanban y su propia ejecución, que dentro de
  este workflow duplicaría a Spec-Kit.

## 2. Objetivo

Un repositorio de **skills atómicas, no encadenadas**, más un **CLI compartido de scripts Python**, que:

1. Cubre la parte del workflow donde rinden los modelos fuertes: contexto, plan, paquetes para PB, auditoría de PB, preparación
   de Spec-Kit y review independiente.
2. Tiene una **skill guía** que lee el estado real (repo, Jira, Confluence, GitHub y copias locales de los chats de PB) y dice los
   próximos pasos, **dónde** hacerlos (harness, PB, Cursor o humano), con qué modelo y con qué comando.
3. Alimenta un **dashboard HTML standalone** al que se le arrastra un JSON y grafica qué hay, dónde está, qué falta, velocidad,
   calidad y consumo de LLM por marca y modelo.

Criterios de éxito:

- El operador puede abrir una sesión, preguntar "¿qué sigue?" y recibir pasos concretos sin releer la documentación.
- No se pierde ningún evento de telemetría de Spec-Kit: todo lo de aguas abajo sigue pasando por sus comandos oficiales.
- Se gasta lo mínimo del pool de Cursor (escaso); Claude y Codex (abundantes) hacen el razonamiento.
- El dashboard muestra el trabajo privado con evidencia enlazada (commits, PRs, issues) y el consumo de cada modelo.

## 3. No objetivos

- Ejecutar implementación propia. Spec-Kit implementa; `wow` nunca reemplaza un comando `/spec-kit.*`.
- Publicar en Jira o Confluence. Publica Product Brain; cierra Spec-Kit (`/sync-status`). `wow` solo lee.
- Un kanban vivo de punta a punta. El kanban propio existe solo aguas arriba (ver D3).
- Compatibilidad con los planes, el `.ic/` o el CLI de `ic` v1/v2.
- Ledger de auditoría propio, registry de worktrees, gates sobre prosa.

## 4. Decisiones

| ID | Decisión | Origen |
|---|---|---|
| D1 | Enfoque A: skills atómicas finas + un CLI compartido `wow`. Ninguna skill invoca a otra; la guía solo recomienda. | operador |
| D2 | Audiencia: uso personal primero, portable para el equipo después (`npx skills add`, sin rutas ni cuentas hardcodeadas, config por archivo y variables). | operador |
| D3 | El kanban propio (manifiesto) es solo *upstream*: es la verdad hasta exportar a PB y después se congela. Aguas abajo mandan Jira (épicas e historias) y Spec-Kit (`tasks.md`). | decidido con los criterios del operador: no perder monitoreo de Spec-Kit y no gastar Cursor |
| D4 | El estado de PB se obtiene de copias locales de los chats de PRD, RFC y cada épica, que el operador guarda en el repo. PB no tiene API conocida. | operador |
| D5 | Los scripts deciden y el LLM interpreta. Todo lo contable (fase, AC faltantes, rondas, tokens) lo calcula un script y lo devuelve en JSON. | diseño |
| D6 | Un solo protocolo de review con conjuntos de anclas (heredado de `ic` v2 D5/D6/D7/D8): BLOCKER sin ancla válida pasa a WARNING; ronda nueva solo con BLOCKER válido y diff cambiado; tope de 3 rondas y luego HITL. | `ic` v2 |
| D7 | Orden de revisores: `codex → copilot → HITL`. Sin `cursor` (gasta el pool) y sin `claude` (el anfitrión es Claude: sería autorrevisión). | diseño |
| D8 | Tres estados de salida en todo script: `0` OK, `1` hallazgos, `2` no pude evaluar. Un `2` nunca se reporta como verde. | regla del quality gate de Spec-Kit |
| D9 | Scripts solo con biblioteca estándar, compatibles con Python 3.9, ejecutables desde una carpeta copiada. | `ic` v2 |
| D10 | Idioma: skills, código, schemas, mensajes del CLI y **todo el dashboard HTML** en inglés; documentación humana (README, guías, este spec) en castellano. | operador |
| D11 | El snapshot (`progress.json`) no contiene código, prompts ni contenido de chats: solo ids, links, estados y números. Es seguro de compartir. | diseño |
| D12 | Las métricas sin dato son `null`/`unknown` y se muestran como "sin dato", nunca como cero. Cada número lleva su fuente. | diseño |

## 5. Arquitectura

### 5.1 Repositorio de distribución

```
WayOfWork/
├── skills/
│   ├── wow-guide/SKILL.md
│   ├── wow-context/SKILL.md
│   ├── wow-plan/SKILL.md
│   ├── wow-review/SKILL.md
│   ├── wow-pack/SKILL.md
│   ├── wow-pb-audit/SKILL.md
│   └── wow-sk-prep/SKILL.md
├── wow/                      CLI compartido (stdlib, Python 3.9+)
│   ├── wow                   entrypoint: `wow <subcommand>`
│   ├── state.py              fase por plan y por épica, próximos pasos
│   ├── snapshot.py           state + usage + links → progress.json
│   ├── usage.py              colector y normalizador de consumo de LLM
│   ├── sources/              repo.py · speckit.py · jira.py · confluence.py · github.py · pbchat.py
│   ├── manifest.py           schema, validate, lint del kanban upstream
│   ├── review.py             protocolo anclado, rondas, invocación del revisor
│   ├── pack.py               plantillas PRD / RFC / épica + preámbulo
│   ├── runwu.py              wrapper de cursor-agent que guarda el JSON de uso
│   └── config.py             .wow/config.json + credenciales IC_JIRA_* (ver sección 10)
├── schemas/                  manifest · progress · usage-record · review-summary · pbchat-audit · config
├── dashboard/wow-dashboard.html
├── install.sh                instala `wow` en el PATH
├── tests/                    unittest + fixtures por fase
└── README.md                 (castellano)
```

Cada `SKILL.md` tiene como máximo ~80 líneas y declara: cuándo usarla, qué lee, qué produce y qué subcomando de `wow` dispara.

### 5.2 Lo que `wow` agrega al proyecto donde se usa

El proyecto es el repo padre de Spec-Kit (workspace con repos hijos como submódulos).

```
.wow/config.json          configuración (versionada)
.wow/reviews/             salidas crudas de cada ronda de review (gitignored)
wow/
├── context-pack/         facts.md · metrics.md · decisions.md · contracts.md · pending-owner.md
├── plan/                 PLAN.md (Brief) · manifest.json
├── pb/                   prd.md · rfc.md · epic-<ID>.md  (paquetes)
│   └── chats/            prd.md · rfc.md · epic-<ID>.md  (copias locales de PB) + *.audit.json
├── sk/<feature>/         clarify-answers.md · plan-draft.md
├── reviews/<ref>.json    resúmenes de review (versionados)
└── progress.json         snapshot para el dashboard
harness/runs/             salida JSON de cada corrida de cursor-agent (uso de Cursor)
```

### 5.3 Reglas de arquitectura

1. **Los scripts deciden, el LLM interpreta** (D5).
2. **Solo lectura hacia afuera**: Jira, Confluence y GitHub se leen, nunca se escriben.
3. **Nunca reemplaza un comando de Spec-Kit**: la guía entrega el comando oficial y el modelo; no lo emula.
4. **El único efecto externo es `wow run-wu`**, que ejecuta `cursor-agent` cuando el operador lo pide.

## 6. Estado y skill guía

### 6.1 Granularidad

Las fases 0–2 son del plan; las fases 3–6 son por épica. El mapeo de fases es el de `way-of-work.html`:
0 preparación · 1 plan · 2 paquetes · 3 Product Brain · 4 Spec-Kit: sync y ratificación · 5 implementación · 6 cierre.

### 6.2 Señales por fase (todas verificables por script)

| Fase | Cumplida cuando | Fuente |
|---|---|---|
| 0 | Existe `context-pack/facts.md` y `pending-owner.md` no tiene ítems sin marcar (o están aceptados como `[SIN DEFINIR]`). | repo |
| 1 | El manifiesto valida contra el schema y `plan.readiness.verdict` es `approved`. | repo |
| 2 | Existen los paquetes `prd`, `rfc` y uno por épica, y la cabecera de cada uno lleva el hash del manifiesto vigente. Si no coincide, el paquete está desactualizado. | repo |
| 3 (épica) | La copia del chat tiene marca de cierre, su auditoría es `approved`, y la épica existe en Jira con tantas historias como tareas tiene en el manifiesto. | `wow/pb/chats/` + Jira |
| 4 (épica) | Existe un `specs/NNN/spec.md` con `**Jira Epic:** <KEY>`, más `plan.md`, `tasks.md` y `work-units.json`. | repo (Spec-Kit) |
| 5 (épica) | Progreso de `[x]` en `tasks.md` y, por historia, el resumen de `wow-review` con conjunto `story`. | repo |
| 6 (épica) | Todas las tareas en `[x]`, historias en Done en Jira y review con conjunto `epic` aprobado. | repo + Jira |

### 6.3 Salida de `wow state`

```json
{
  "plan": {"id": "0001-iris-v2", "phase": 2, "stale_packets": ["epic-E2"]},
  "epics": [
    {"id": "E1", "jira": "IRIS-40", "phase": 5, "progress": "7/12"},
    {"id": "E2", "jira": null, "phase": 3}
  ],
  "blockers": ["owner: North Star undecided (blocks E2 stories)"],
  "next_steps": [
    {"epic": "E1", "action": "implement WU-008", "where": "cursor",
     "model": "composer-2.5", "command": "wow run-wu WU-008",
     "why": "WU-007 approved and reviewed; WU-008 has no pending dependencies"}
  ],
  "sources": {"jira": "ok", "confluence": "unavailable", "github": "ok"}
}
```

### 6.4 Reglas de la guía

- **Dónde** sale de una tabla fija por paso: `harness`, `product-brain`, `cursor`, `human`. Los modelos por defecto salen del PDF
  "Modelos recomendados" y se pueden pisar en `.wow/config.json`.
- **Prioridad**: primero bloqueos humanos, después lo que destraba más trabajo, al final lo que gasta Cursor (para agrupar esos
  pasos).
- **Fuente caída**: la fase que depende de ella queda `unknown` con el motivo.
- **Nunca ejecuta**: recomienda como máximo 3 próximos pasos.

## 7. Snapshot, métricas y consumo de LLM

### 7.1 `wow snapshot`

Escribe `wow/progress.json` con:

- `current`: el estado de 6.3 enriquecido con **links** (issue en Jira, PR y commits en GitHub, página de Confluence, archivo en el
  repo) y una lista `missing` por épica.
- `history`: un punto compacto por snapshot (fecha, fase por épica, historias Done, WU aprobadas, rondas de review). Permite calcular
  velocidad sin base de datos.
- `usage`: registros normalizados de consumo (7.3).

### 7.2 Métricas

| Métrica | Fuente |
|---|---|
| Throughput (historias Done por semana) | Jira (fecha de transición) |
| Lead time por historia (creada → Done) | Jira |
| Burn-up por épica | `history` |
| Iteraciones por WU y aprobación al primer intento | resúmenes de `wow-review` |
| Rondas de review y escalados a HITL | `wow-review` |
| Tokens in/out, cache, reasoning, tiempo de respuesta por marca y modelo | `usage` |
| Reparto de consumo Claude/Codex vs Cursor por fase | `usage` + fase del `ref` |
| Costo estimado | tokens × tabla de precios de config (marcado como estimado, con fecha de la tabla) |

### 7.3 `wow usage`: fuentes verificadas

Verificado en la máquina del operador el 2026-10-01:

| Herramienta | Modelo | Tokens | Tiempo | Granularidad | Fuente |
|---|---|---|---|---|---|
| Claude Code | `message.model` | `input_tokens`, `output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens` | timestamp por mensaje | mensaje | `~/.claude/projects/<proyecto>/*.jsonl` |
| Codex | de la sesión | `input_tokens`, `cached_input_tokens`, `output_tokens`, `reasoning_output_tokens` | timestamps de eventos | turno | eventos `token_count` en `~/.codex/sessions/**/*.jsonl` (o `codex exec --json`) |
| Cursor headless | no lo reporta: se toma del `--model` que pasa `wow run-wu` | `inputTokens`, `outputTokens`, `cacheReadTokens`, `cacheWriteTokens` | `duration_ms` | tarea | salida de `cursor-agent --output-format json` |
| Cursor interactivo | `model_id` | los 4 contadores | timestamps | turno | hook `stop` (documentado por Spec-Kit; **no verificado** en el IDE) |
| Product Brain | visible en la copia del chat | no disponible (opcional: caracteres ÷ 4 como `[ESTIMACIÓN]`) | aproximado | mensaje | copia local del chat |

Registro normalizado:

```json
{"ts": "...", "vendor": "anthropic", "tool": "claude-code", "model": "claude-opus-5-5",
 "tokens_in": 1200, "tokens_out": 340, "cache_read": 900, "cache_write": null, "reasoning_out": null,
 "duration_ms": 8100, "scope": "message", "ref": "E1/WU-008", "source": "claude-transcript"}
```

Atribución: Claude por carpeta de proyecto, Codex por el `cwd` de la sesión, Cursor por el `ref` que anota `wow run-wu`. Lo no
atribuible queda `ref: null`; nunca se reparte a ojo. Solo se copian números, nunca contenido.

Hallazgo que motiva `wow run-wu`: en `cursor-agent -p` los hooks de Cursor no reciben modelo ni tokens (probado), pero la salida
JSON sí trae tokens y duración. Sin guardar esa salida, el gasto de Cursor en modo unattended se pierde.

## 8. Dashboard (`dashboard/wow-dashboard.html`)

- Un solo archivo HTML, sin servidor, sin dependencias externas, sin red. Una Content-Security-Policy bloquea toda conexión saliente.
- **Todo en inglés** (D10), incluidas las etiquetas.
- Entrada: uno o varios `progress.json` por drag-and-drop o selector de archivo. Con varios aparece una vista de portfolio.
  Valida `schema_version` y avisa si no coincide.
- Paneles:
  1. **Phase map**: épicas × fases 0–6, fase actual resaltada, bloqueos.
  2. **What's missing and where**: próximos pasos con insignia de lugar (harness / Product Brain / Cursor / human), modelo y botón
     para copiar el comando.
  3. **Where things live**: links a Jira (estado), GitHub (PR, checks), Confluence y repo.
  4. **Velocity**: burn-up por épica, throughput semanal, lead time.
  5. **Quality**: rondas de review por historia, aprobación al primer intento, HITL.
  6. **LLM usage**: tokens in/out por marca y modelo, reparto Claude/Codex vs Cursor por fase, costo estimado, tiempo de respuesta
     (mediana y p95) por modelo.
  7. **Product Brain**: PRD, RFC y épicas: cerrado o no, resultado de la auditoría.
- Reglas visuales: "no data" rayado con motivo (D12); fuente de cada número en el tooltip; el pool de Cursor siempre con el mismo
  color propio; costos marcados como estimados; tema claro y oscuro; imprimible.
- Implementación con la skill `dataviz` (validador de paleta para ambos temas).

## 9. Las siete skills

| Skill | Cuándo | Script | LLM | Produce |
|---|---|---|---|---|
| `wow-guide` | "¿qué sigue?", al abrir sesión | `wow snapshot` | explica 3 próximos pasos y bloqueos | `wow/progress.json` |
| `wow-context` | fase 0, o cambió el repo | `wow context scan`, `wow context check` | Opus redacta hechos con id `C#`, etiqueta y fuente | `wow/context-pack/` |
| `wow-plan` | iniciativa nueva o cambio antes de exportar | `wow plan init`, `wow manifest validate`, `wow manifest lint`, `wow plan freeze` | Opus: brainstorming de a una pregunta, Brief, descomposición | `wow/plan/` |
| `wow-review` | cualquier revisión independiente | `wow review --set <anchors> --ref <id>` | ninguno del anfitrión: revisa otro modelo | `wow/reviews/<ref>.json` |
| `wow-pack` | fase 2 | `wow pack prd\|rfc\|epic --id <ID>` | Opus llena solo secciones narrativas marcadas | `wow/pb/*.md` |
| `wow-pb-audit` | después de cada chat de PB | `wow pbchat parse` | Codex: inventos vs context pack y lista conocida → correcciones para pegar | `wow/pb/chats/<doc>.audit.json` |
| `wow-sk-prep` | antes de cada paso de Spec-Kit | `wow sk status`, `wow sk cmd <step>`, `wow run-wu <WU>` | Opus: respuestas de `clarify` y `plan-draft.md` | `wow/sk/<feature>/`, `harness/runs/` |

### 9.1 `wow-review`

Conjuntos de anclas:

| Conjunto | Anclas | Paquete |
|---|---|---|
| `readiness` | R1–R5 (heredadas de `ic` v2) | PLAN.md + manifest |
| `claims` | ids `C#` del context pack o del RFC | documento + código citado |
| `story` | AC de una historia | diff de la WU + salida de verificación |
| `epic` | `done_when` de la épica | diff acumulado |

Formato de salida exigido al revisor (parseado por `review.py`):

```
VERDICT: APPROVED | CHANGES_REQUIRED
BLOCKER <anchor-id> <path:line> — <what fails and why it breaks the anchor>
WARNING <path:line> — <...>
NIT — <...>
```

Reglas mecánicas: BLOCKER con ancla inexistente → WARNING; aprobado con cero BLOCKER válidos; ronda nueva solo con BLOCKER válido y
hash de diff distinto; 3 rondas con BLOCKER → `hitl`. Revisor según D7; sin revisor disponible, sale con `2` y pide decisión humana.

Chequeo previo (reemplaza al comando `dry-run` de `ic`): antes de la primera ronda, `review.py` le pide al revisor que responda
exactamente `OK`. Si la salida, sin espacios, no es `OK`, el revisor se considera no disponible y se prueba el siguiente de D7.

### 9.2 `wow-plan`: manifiesto congelado

Tras exportar cada épica en PB, `wow plan freeze --epics E1=IRIS-40[,E2=…]` registra las keys en `plan.export.epics` y fija
`plan.export.frozen: true`. Desde ahí, toda escritura falla con `1`, salvo `--reopen "<motivo>"`. El mensaje
dirige al camino de cambio de alcance: Artifact Engine de PB + `/spec-kit.amend`.

### 9.3 `wow-pb-audit`: lista de inventos conocidos

Semilla, tomada de la primera iniciativa del operador: modelo de marketplace (comprador/vendedor), North Star con targets, SLA de
disponibilidad, API Gateway, Okta/OAuth, owners para preguntas abiertas, plazos. Más: ítems de checklist marcados como cumplidos sin
cita, ids de AC perdidos, etiquetas `[MEDIDO]`/`[ESTIMACIÓN]`/`[SIN DEFINIR]` alteradas.

### 9.4 `wow-sk-prep`: ahorro de Cursor

Toda llamada a Cursor recibe insumos pre-masticados por Opus. `wow sk cmd` arma el comando `cursor-agent` exacto con el modelo de la
config. `wow run-wu` aísla `TMPDIR` por corrida (evita que se pisen las sesiones de telemetría de Spec-Kit en paralelo) y guarda
`--output-format json` en `harness/runs/`.

## 10. Contratos de datos

Todos en `schemas/` como JSON Schema, con `schema_version`.

| Schema | Contenido clave |
|---|---|
| `manifest` | modelo de `ic` v2 (plan, épicas con `done_when`, tareas con `acceptance`, `depends_on`, subtareas) + `estimate`, `priority`, `labels` por tarea + `plan.readiness {verdict, rounds}` + `plan.export {frozen, at, epics}` |
| `progress` | `current`, `history[]`, `usage[]` |
| `usage-record` | 7.3; campos sin dato en `null` |
| `review-summary` | `ref, anchor_set, rounds[{n, verdict, blockers[{anchor, path_line, text}], warnings, diff_hash}], final` |
| `pbchat-audit` | `doc, verdict (approved\|changes_required\|unknown), closed, completion_pct, open_questions[], expected_anchors[], missing_anchors[], unsupported_checks[], inventions[], corrections_to_paste` |
| `config` | Proyecto Jira y espacio Confluence, orden de revisores, modelos por paso, tabla de precios con fecha. **Sin credenciales** |

Credenciales: se leen de variables de entorno con prefijo `IC_JIRA_` (`IC_JIRA_BASE_URL`, `IC_JIRA_USER_EMAIL`,
`IC_JIRA_API_TOKEN`, `IC_JIRA_PROJECT_KEY`, `IC_JIRA_EPIC_CHILD_MODE`, `IC_JIRA_FIELD_EPIC_LINK`, `IC_JIRA_USER_NAME`), los mismos
nombres que ya usa `ic`. Orden de resolución: entorno del shell → `.env.local` del proyecto (gitignored, permisos 600) →
`JIRA_*` de `.spec-kit/.env` como fallback. Ningún script imprime ni registra sus valores.

## 11. Manejo de errores

- Estados de salida según D8.
- Fuente caída: `unavailable` con motivo; el snapshot se genera igual; lo dependiente queda `unknown`.
- Schema de otra versión: rechazo con motivo (scripts); aviso y render parcial (dashboard).
- Sin revisor: `2` y decisión humana.
- Manifiesto congelado: `1` con el camino de cambio de alcance.
- Ningún script escribe en Jira, Confluence ni en artefactos de Spec-Kit.

## 12. Tests

- Comportamiento de scripts, nunca prosa: parsing de veredictos, reglas de rondas, detección de fase, normalización de cada fuente de
  uso (con transcripts recortados y anonimizados), validación de schemas, manifiesto congelado.
- Fixtures por fase: mini-repos que representan un proyecto en cada fase 0–6; `wow state` debe devolver exactamente el próximo paso
  esperado.
- Dashboard: render headless con tres `progress.json` de ejemplo (vacío, parcial con fuentes caídas, completo con varias épicas).
- Comportamiento del LLM (la guía no ejecuta; el brainstorming pregunta de a una cosa; la auditoría detecta los inventos de la
  semilla): evals manuales, fuera de CI.
- `unittest` de la biblioteca estándar; `pytest` opcional.

## 13. Relación con `ic`

- `ic` v2 (`~/CurrentCode/individual-contributor-v2`, plan `0001-ic-v2`, sin tareas empezadas) **no se implementa**: queda como
  referencia. Se conservan su modelo de manifiesto, el protocolo de review anclado (D5–D9 de la v2), el checklist R1–R5 y el Brief.
- Se descartan para este repo: ejecución propia (`execute`), `jira-sync` (publica PB), worktree status, `critique`, `dry-run` como
  comando separado (queda como chequeo dentro de `wow-review`).
- `ic` v1 sigue disponible para otros proyectos fuera de este workflow.

## 14. Riesgos y preguntas abiertas

| Tema | Estado |
|---|---|
| Gobierno de datos: mandar código de la empresa a cuentas personales de Claude y Codex | Lo decide seguridad/PDLC. Si no se permite, el anfitrión pasa a `cursor-agent` con Opus y el revisor al habilitado por la org. |
| PB sin API | Mitigado con copias locales de chats (D4). Si PB publica una API, `sources/pbchat.py` se reemplaza sin tocar el resto. |
| Hook `stop` de Cursor interactivo | No verificado en el IDE; hasta probarlo, el consumo interactivo de Cursor puede quedar `unknown`. |
| Formato de las copias de chat de PB | A definir con la primera copia real; el parser debe tolerar variaciones (marcas "100%", "por cerrado"). |
| Una épica por chat de Epic en PB | No verificado; la señal de fase 3 asume una épica por chat. |
| Cambios de formato en transcripts de Claude/Codex o en la salida de `cursor-agent` | Cada normalizador tiene fixtures; un formato desconocido da `2`, no datos inventados. |

## 15. Orden de construcción sugerido

1. Schemas + `manifest.py` + tests.
2. `sources/` (repo, speckit, jira, github, pbchat) + `state.py` + fixtures por fase.
3. `usage.py` + `snapshot.py` + fixtures de transcripts.
4. `review.py` + tests de rondas.
5. `pack.py`, `runwu.py`, subcomandos `sk` y `context`.
6. Las siete `SKILL.md`.
7. Dashboard + render headless.
8. README en castellano y `install.sh`.

## 16. Referencias

- `SPECKIT/docs/site/index.html` (evidencia de Spec-Kit, telemetría, Jira, Product Brain) y `way-of-work.html` (workflow).
- `~/CurrentCode/individual-contributor-v2/docs/superpowers/specs/2026-10-01-ic-v2-design.md`.
- `~/CurrentCode/individual-contributor/skills/ic/references/reviewer-matrix.md` y `jira-sync.md`.
