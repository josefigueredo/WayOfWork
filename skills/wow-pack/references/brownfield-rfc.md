# Brownfield RFC prompt (Product Brain 100% on first paste)

Source of truth: Product Brain backend (`josefigueredo/acme-agent`): `api/src/db/base-templates.ts` →
`RFC_TEMPLATE_CONTENT`, `api/src/modules/documents/completion.ts`, and `api/src/modules/agents/agent-prompts.config.ts`
→ `RFC_PROMPT` (EM Agent). Re-check them when Product Brain changes; mirrored on 2026-10-02.

What matters from Product Brain's side:
- Same deterministic scoring as the PRD: any non-empty text fills a field (`[SIN DEFINIR] …`,
  `No aplica: …` and `Ninguna` count). Each numbered table/list is one unit, filled with one complete row.
  `open_questions` needs question + owner + status on every row.
- The template has a FIXED `### API Gateway` section and `### SLA`. Its model fills them by default,
  which is where "API Gateway" and invented SLAs came from. Fill them with the truth (`No aplica: …` / `[SIN DEFINIR] …`).
- The EM Agent will not draft before it has: stack, authentication, high-level architecture, deployment,
  expected volume and rollout plan. It prefers indexed code over the PRD for API contracts
  ("Código indexado > RFC/PRD previo > inferencia"), so every contract must cite the source file.
- Its Phase 3 checklist asks for: quantified problem, glossary, business impact with numbers, measurable
  goals with dates, detailed non-goals, a complete architecture diagram, verified API request/response,
  data model with types/constraints/indexes, rollout with feature flags and phases, concrete rollback,
  resilience mechanisms, risks with mitigation, alternatives with pros/cons, open questions, and "a developer
  could start coding without asking". Answer each honestly; do not claim mechanisms that do not exist.

---

## Prompt (paste into Claude Opus / Codex with the context pack and repos attached)

You are a Senior Engineering Manager / Tech Lead writing the RFC of a change to an EXISTING system.
It will be pasted into Product Brain, whose EM Agent maps it field by field onto a fixed template and
scores completion per field, and later derives Jira epics and stories from it. Fill every field with
true, verifiable content; where information is missing, write an explicit undefined marker.

INPUTS (only these are sources of truth):
- The approved PRD (`wow/pb/prd.md` after its Product Brain chat closed and `wow pbchat audit prd` passed).
- `wow/context-pack/*.md` (tagged, sourced claims), `wow/plan/PLAN.md`, `wow/plan/manifest.json`.
- Spec-Kit discovery (`discovery/architecture.md`) and the repositories: read the code to verify
  endpoints, DTOs, tables, configuration and deployment. Code beats any document.

RULES:
1. Output Spanish (professional). Output ONLY the document, starting at `# `.
2. Reproduce the template below EXACTLY: same headings (including their numbering), same order, same
   tables and columns. Replace every `{{…}}`; none may remain.
3. Brownfield framing: describe the CURRENT design first and the CHANGE second inside each section
   ("Hoy: … / Cambio: …"). "Coexistencia y Fallback" is mandatory content: how old and new run together,
   what happens on failure, how data stays consistent during the transition.
4. Every component, repo, endpoint, field, table, index, alarm or limit cites its source in backticks
   (`bff/src/routes/cases.ts:42`). Anything you cannot verify in code: `[TBD - verificar en código/Swagger]`
   for API fields, `[SIN DEFINIR] — <qué falta y quién lo decide>` elsewhere, plus a Preguntas Abiertas row.
5. API Gateway: if there is none, write `No aplica: no hay API Gateway; la entrada es <componente real> (fuente)`
   in each of its three cells. Never describe a gateway that is not in the code.
6. SLA: only an SLA/SLO that exists in a document or config; otherwise `[SIN DEFINIR] — no hay SLA acordado; lo decide <rol>`.
7. Resilience: list only mechanisms present in code/config (retries with their numbers, timeouts, DLQs,
   alarms). If a checklist mechanism (circuit breaker, rate limit) does not exist, say so explicitly.
8. API specs: method, path, where params go (path/query/body), request and response exactly as the DTO/handler
   defines them, error responses only if present in code. If the change has fewer than three APIs, the unused
   letter blocks say `No aplica: el cambio expone <n> API(s)`. If it has more, add `#### D.` blocks with the same shape.
9. Data model: existing entities/keys/indexes first (cited), then the change; types, constraints, indexes, and
   migration/backfill if any. `{{data_model_sql}}` holds the DDL/key schema or `No aplica: <motor> sin esquema SQL; ver claves arriba`.
10. Milestones map to the manifest epics (E1, E2…), with estimates only if the manifest has them,
    otherwise `[SIN DEFINIR]`. Keep AC/E ids verbatim where you reference acceptance criteria.
11. Rollout: feature flags and phases that actually exist or are part of this change; rollback must be concrete
    and executable without a new deploy when possible (flag off, traffic switch, data restore). If neither is
    defined: `[SIN DEFINIR] — <qué falta>` and an open question; never invent percentages or dates.
12. Alternativas Consideradas: a table "Alternativa | Pros | Contras | Decisión y motivo" with the real discarded
    options from `decisions.md` / ADRs (cited).
13. Preguntas Abiertas: one row per open decision; Owner = deciding ROLE, Estado = `Abierta`. If none: one row
    `| 1 | Ninguna | Tech Lead | Cerrada |` (all columns filled).
14. Prepend nothing; but make sure the sections jointly state stack, authentication, high-level architecture,
    deployment, expected volume and rollout, because the EM Agent checks those six before drafting.
15. Before finishing, run the CHECKLIST at the end and fix the document until every line passes. Do not print it.

TEMPLATE (fill it):

# {{rfc_id}}: {{title}}

| Metadatos | Detalle |
| :--- | :--- |
| Estado | {{status}} |
| Autores | {{authors}} |
| Version | {{version}} |
| Target Date | {{target_date}} |
| PRD Link | {{prd_link}} |

> Resumen Ejecutivo:
> {{executive_summary}}

---

## 1. Contexto y Alcance (Context & Scope)

### Definicion del Problema
{{problem_definition}}

### Glosario y Terminos
{{glossary}}

### Impacto en el Negocio
{{business_impact}}

### Objetivos (Goals)
- {{goal}}

### Fuera de Alcance (Non-Goals)
- {{non_goal}}

---

## 2. Diseno de la Solucion (Solution Design)

### Diagrama de Arquitectura
{{architecture_diagram}}

### Componentes Clave
| Componente | Tecnologia | Responsabilidad |
| --- | --- | --- |
| {{component_name}} | {{component_tech}} | {{component_responsibility}} |

### Repositorios
| Repositorio | Tecnologia | Equipo | Descripcion |
| --- | --- | --- | --- |
| {{repo_name}} | {{repo_tech}} | {{repo_team}} | {{repo_description}} |

### API Gateway
| Aspecto | Detalle |
| --- | --- |
| Tecnologia | {{api_gateway_tech}} |
| Funcionalidad | {{api_gateway_function}} |
| Configuracion | {{api_gateway_config}} |

### Coexistencia y Fallback
{{coexistence_strategy}}

### Especificaciones de API (Contrato)

#### A. {{api_a_name}}
- Endpoint: `{{api_a_endpoint}}`
- Descripcion: {{api_a_description}}
- Request:
{{api_a_request}}
- Response:
{{api_a_response}}

#### B. {{api_b_name}}
- Endpoint: `{{api_b_endpoint}}`
- Descripcion: {{api_b_description}}
- Request:
{{api_b_request}}
- Response:
{{api_b_response}}

#### C. {{api_c_name}}
- Endpoint: `{{api_c_endpoint}}`
- Descripcion: {{api_c_description}}
- Request:
{{api_c_request}}
- Response:
{{api_c_response}}

### Modelo de Datos
{{data_model_description}}

{{data_model_sql}}

---

## 3. Plan de Implementacion

### Hitos (Milestones)
| Fase | Entregable | Estimacion |
| --- | --- | --- |
| {{milestone_phase}} | {{milestone_deliverable}} | {{milestone_eta}} |

### Estrategia de Rollout
{{rollout_strategy}}

### Plan de Rollback
{{rollback_plan}}

### Riesgos y Mitigacion
| Riesgo Detectado | Plan de Mitigacion |
| --- | --- |
| {{risk_name}} | {{risk_mitigation}} |

### Dependencias
| Servicio/Equipo | Necesidad | Estado |
| --- | --- | --- |
| {{dependency_team}} | {{dependency_need}} | {{dependency_status}} |

---

## 4. Consideraciones Transversales

### Seguridad
{{security}}

### Calidad
{{quality_considerations}}

### Escalabilidad
{{scalability}}

### SLA
{{sla}}

### Resiliencia y Observabilidad
{{resilience_observability}}

---

## 5. Alternativas Consideradas
{{alternatives}}

---

## 6. Preguntas Abiertas
| # | Pregunta/Decision | Owner | Estado |
| --- | --- | --- | --- |
| 1 | {{question}} | {{owner_role}} | Abierta |

FIELD GUIDANCE FOR AN EXISTING SYSTEM:
- `rfc_id`: next id in the team's RFC numbering if it exists in the repo/docs, else `RFC-[SIN DEFINIR]`.
- `status`: `Borrador`. `version`: `0.1`. `target_date`: from the owner or `[SIN DEFINIR]`.
- `prd_link`: the Product Brain PRD of this initiative (paste its URL) or `PRD de esta iniciativa en Product Brain`.
- `problem_definition`: the technical side of the PRD problem, with numbers from `metrics.md`.
- `glossary`: domain and system terms used in the RFC (state names, key prefixes, internal service names).
- `architecture_diagram`: Mermaid `flowchart` with EVERY component listed in "Componentes Clave", marking
  new/changed nodes; no node that is not in the code or in this change.
- `security`: real authentication/authorization path (e.g. the actual identity service, cited), secrets handling,
  data classification; explicitly "no es Okta/OAuth" only if relevant to avoid confusion.
- `quality_considerations`: existing test suites and gates (cited) plus what this change adds.
- `scalability`: measured volumes and limits (memory, timeouts, concurrency) with their tags.

CHECKLIST (Product Brain EM Agent Phase 3 plus brownfield gates; all must pass):
- [ ] No `{{` remains; every heading of the template is present, numbered and in order.
- [ ] Problem and business impact are quantified (tagged numbers with sources).
- [ ] Glossary covers every non-obvious term used.
- [ ] Goals are measurable and dated (or `[SIN DEFINIR]` + open question); non-goals are explicit.
- [ ] The diagram contains all key components and only real ones; changed parts are marked.
- [ ] Each API: method, path, param location, request and response as in code (cited) or `[TBD - verificar en código/Swagger]`.
- [ ] The data model has types, constraints and indexes for existing and changed entities.
- [ ] Coexistence/fallback explains old+new running together and failure behaviour.
- [ ] Rollout states real flags/phases or `[SIN DEFINIR]`; rollback is concrete or `[SIN DEFINIR]`, never invented.
- [ ] Resilience lists only existing mechanisms with their numbers; absent ones are stated as absent.
- [ ] Every risk has a mitigation; alternatives have pros, cons and the reason for discarding.
- [ ] The six EM-Agent prerequisites (stack, auth, architecture, deploy, volume, rollout) are answerable from the text.
- [ ] Every Preguntas Abiertas row has question + owner role + estado; every `[SIN DEFINIR]` above has a row.
- [ ] A developer could start the first epic without asking; if not, the missing detail is an open question.
- [ ] No API Gateway, Okta/OAuth, SLA, circuit breaker, owner name or date that is not in the inputs.

## How to paste it in Product Brain

1. Attach or index the repositories in Product Brain (ZIP or integration): the EM Agent verifies contracts against
   indexed code and corrects the RFC when they differ, which is what you want.
2. Open the RFC step (the PRD is injected automatically). First message: `wow/pb/preamble.md`.
   Second: "Comparto el RFC ya redactado sobre el sistema existente, verificado contra el código; mapealo campo
   por campo sin resumir" + the document.
3. The EM Agent requires 3–4 Q&A rounds in Phase 1; answer them from the RFC itself ("está en la sección 2,
   Componentes Clave") and confirm its summary with "dale".
4. Trust only `**Completitud del documento:** N%` from the backend. Answer the listed pending fields.
5. In Phase 3, answer each ⚠️ with evidence or move it to Preguntas Abiertas; never accept a ✅ without a citation.
6. Copy the chat to `wow/pb/chats/rfc.md` and run `wow pbchat audit rfc --deep`.
