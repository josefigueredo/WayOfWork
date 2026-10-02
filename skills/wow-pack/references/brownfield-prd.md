# Brownfield PRD prompt (Product Brain 100% on first paste)

Source of truth for the rules below: Product Brain backend (`josefigueredo/acme-agent`,
`api/src/db/base-templates.ts` → `PRD_TEMPLATE_CONTENT`, `api/src/modules/documents/completion.ts`,
`api/src/modules/documents/pipeline/open-questions-validation.ts`, `api/src/modules/agents/agent-prompts.config.ts`
→ `PRD_PROMPT`). Re-check them when Product Brain changes; this file mirrors the template as read on 2026-10-02.

How Product Brain scores the PRD (deterministic, not the LLM):
- Completion = filled template fields / expected fields. A field is filled by ANY non-empty text,
  including `[SIN DEFINIR] …` and `No aplica: …`. An unreplaced `{{placeholder}}` or empty text is empty;
  text mixed with a `{{placeholder}}` counts as half.
- Every numbered table (KPIs, scope, risks, NFR, dependencies, users) collapses into one unit:
  filled when at least ONE row has every column filled.
- `open_questions` is strict: EVERY row needs question, owner and status, or the field is partial.
- The template is marketplace-shaped (buyer, seller, ops; "Experiencia comprador", "Operacion vendedor").
  Product Brain's example data is a marketplace, which is why its model invents one. Fill those slots
  with the real roles or with `No aplica: <motivo>`, never by adapting the domain.

---

## Prompt (paste into Claude Opus / Codex with the context pack attached)

You are writing the PRD of a change to an EXISTING system. It will be pasted into Product Brain,
whose PRD Agent maps it field by field onto a fixed template and scores completion per field.
Your job is to produce a document that (a) fills every template field with true content and
(b) never invents a fact. Those two goals only conflict when information is missing; then you
write an explicit undefined marker, which Product Brain counts as filled and a reader counts as honest.

INPUTS (only these are sources of truth):
- `wow/context-pack/facts.md`, `metrics.md`, `decisions.md`, `contracts.md`, `pending-owner.md`
  (claims tagged [MEDIDO] / [ESTIMACIÓN] / [SIN DEFINIR] with `fuente: path:line`).
- `wow/plan/PLAN.md` (Brief) and `wow/plan/manifest.json` (epics, tasks, acceptance criteria).
- Spec-Kit discovery output if present (`discovery/architecture.md`): it describes the REAL system.
- The repositories themselves, for anything you need to verify.

RULES:
1. Output Spanish (Rioplatense neutral, professional). Output ONLY the document, starting at `# `.
2. Reproduce the template below EXACTLY: same headings, same order, same tables and columns, no
   heading renamed or removed, no section added between them. Replace every `{{…}}`; none may remain.
3. Brownfield framing: "Contexto" describes the current system with file citations in backticks;
   "Problema" is the measured pain of the current system; baselines come from measured data
   ([MEDIDO], with where/when/how). The PRD states WHAT changes and WHY, never HOW (that is the RFC).
4. Unknown information: write `[SIN DEFINIR] — <qué falta y quién lo decide>` in that field AND add
   a row for it in "Preguntas Abiertas". Never a plausible number, owner, date, SLA or provider.
5. Template slots that do not apply to this domain (buyer/seller/marketplace dimensions, a third user
   type that does not exist): write `No aplica: <motivo concreto>`. Do not reinterpret the domain to fit.
6. Tables: fill as many rows as there are real items (at least one complete row). Do not pad with
   invented rows; leave unused template rows out entirely. Every kept row has all columns filled.
7. KPIs: Baseline = measured value with its tag; Target and Plazo = the owner's decision if it exists,
   otherwise `[SIN DEFINIR] — decide el owner`. The North Star goes as the first KPI row.
8. Preguntas Abiertas: one table row per open decision, with Owner = the ROLE that decides
   (e.g. "Owner de producto", "Tech Lead de <equipo>"), never an invented person, and Estado = `Abierta`.
   Carry every unchecked item of `pending-owner.md` here.
9. Keep acceptance ids from the manifest (`AC1`, `E1.C1`) verbatim inside "Requerimientos Clave".
10. Self-contained: no "ver documento X" without the content; links only as citations next to content.
11. Before finishing, run the CHECKLIST at the end and fix the document until every line passes.
    Do not print the checklist.

TEMPLATE (fill it):

# {{title}}

| Autor | {{author}} |
| --- | --- |
| Vertical | {{vertical}} |
| Q / Ano | {{quarter_year}} |
| Tipo de Iniciativa | {{initiative_type}} |
| Prioridad | {{priority}} |
| Estado del PRD | {{prd_status}} |

## Resumen Ejecutivo
{{executive_summary}}

**Por que ahora**: {{why_now}}

**Resultado esperado**: {{expected_outcome}}

---

## Vision y Estrategia

### Alineacion con Roadmap {{roadmap_period}}
{{roadmap_alignment}}

### Valor de Negocio
| Dimension | Impacto |
| --- | --- |
| Experiencia comprador | {{impact_buyer_experience}} |
| Operacion vendedor | {{impact_seller_ops}} |
| Manejo de excepciones | {{impact_exception_handling}} |
| Eficiencia operativa | {{impact_operational_efficiency}} |
| Escalabilidad | {{impact_scalability}} |
| Metricas | {{impact_metrics}} |

### Vision Q2+
{{vision_q2_plus}}

---

## Contexto, Problema y Oportunidad

### Contexto
{{context}}

### Problema
{{problem}}

### Oportunidad
{{opportunity}}

---

## Usuarios Target

### Usuario Primario: {{primary_user_type}}
| Caracteristica | Detalle |
| --- | --- |
| Rol | {{buyer_role}} |
| Necesidad | {{buyer_need}} |
| Caso de uso | {{buyer_use_case}} |
| Dolor actual | {{buyer_pain}} |

### Usuario Secundario: {{secondary_user_type}}
| Caracteristica | Detalle |
| --- | --- |
| Rol | {{seller_role}} |
| Necesidad | {{seller_need}} |
| Caso de uso | {{seller_use_case}} |
| Dolor actual | {{seller_pain}} |

### Usuario Terciario: {{tertiary_user_type}}
| Caracteristica | Detalle |
| --- | --- |
| Rol | {{ops_role}} |
| Necesidad | {{ops_need}} |
| Caso de uso | {{ops_use_case}} |
| Dolor actual | {{ops_pain}} |

---

## Objetivo y Metricas de Exito

### Objetivo
{{objective}}

### KPIs Primarios
| Metrica | Baseline | Target | Plazo |
| --- | --- | --- | --- |
| {{kpi_name}} | {{kpi_baseline}} | {{kpi_target}} | {{kpi_deadline}} |

### KPIs Secundarios (Post-lanzamiento)
| Metrica | Target | Rationale |
| --- | --- | --- |
| {{secondary_kpi_name}} | {{secondary_kpi_target}} | {{secondary_kpi_rationale}} |

### Metricas de Salud
| Metrica | Target |
| --- | --- |
| {{health_kpi_name}} | {{health_kpi_target}} |

---

## Alcance y Limitaciones

### In-Scope
| # | Funcionalidad | Descripcion |
| --- | --- | --- |
| 1 | {{in_scope_name}} | {{in_scope_description}} |

### Out-of-Scope
| # | Funcionalidad | Razon | Cuando |
| --- | --- | --- | --- |
| 1 | {{out_scope_name}} | {{out_scope_reason}} | {{out_scope_when}} |

### Riesgos y Mitigaciones
| Riesgo | Probabilidad | Impacto | Mitigacion |
| --- | --- | --- | --- |
| {{risk_name}} | {{risk_probability}} | {{risk_impact}} | {{risk_mitigation}} |

### Supuestos
- {{assumption}}

---

## Requerimientos Clave
{{key_requirements}}

---

## Requerimientos No Funcionales
| Categoria | Requerimiento |
| --- | --- |
| {{nfr_category}} | {{nfr_requirement}} |

---

## Dependencias Criticas
| Servicio/Equipo | Referente | Necesidad | Estado |
| --- | --- | --- | --- |
| {{dependency_team}} | {{dependency_owner}} | {{dependency_need}} | {{dependency_status}} |

---

## Preguntas Abiertas
| # | Pregunta/Decision | Owner | Estado |
| --- | --- | --- | --- |
| 1 | {{question}} | {{owner_role}} | Abierta |

FIELD GUIDANCE FOR AN EXISTING SYSTEM:
- `initiative_type`: e.g. "Evolución de sistema existente", "Modernización", "Feature sobre plataforma existente".
- `prd_status`: `Borrador para revisión` (Product Brain changes it in its own workflow).
- `why_now`: the measured cost of the current situation, with [MEDIDO] figures.
- `context`: current architecture in 4–8 lines citing paths (`backend/app/handler.py`), what already works.
- `problem`: concrete pain with numbers and frequency; who suffers it today and the current workaround.
- `opportunity`: what changes for those users if the gap closes; no technical design.
- Users: real roles of THIS system (analyst, support, platform team…). If only two roles exist, the
  third block is `No aplica: el sistema tiene dos roles (<rol 1>, <rol 2>)` in every cell.
- `impact_buyer_experience` / `impact_seller_ops`: `No aplica: <sistema> no es un marketplace; el impacto
  equivalente está en <fila real>` unless the domain truly has buyers and sellers.
- Risks (probability/impact as Alta/Media/Baja) must include migration/coexistence with the current system.
- NFR: include compatibility with the existing contracts and data, observability already in place, cost limits.
- Dependencies: real teams/services the change touches; Referente = role; Estado = `Confirmada` / `Pendiente`.

CHECKLIST (Product Brain's own Phase 3 list plus the brownfield gates; all must pass):
- [ ] No `{{` remains anywhere; every heading of the template is present, in order.
- [ ] The problem has numbers, frequency and impact, and cites where they were measured.
- [ ] Users are real roles with jobs-to-be-done; non-applicable blocks say `No aplica: …`.
- [ ] The North Star row exists; baseline tagged; target/plazo either decided or `[SIN DEFINIR] — decide el owner`.
- [ ] Secondary KPIs are measurable and have a target or an explicit `[SIN DEFINIR]`.
- [ ] In-Scope is the MVP; Out-of-Scope rows have a reason and a "cuando" (or `[SIN DEFINIR]`).
- [ ] Requerimientos Clave are verifiable and keep the AC/E ids; a Tech Lead can derive stories from them.
- [ ] Risks have probability, impact and mitigation; assumptions are listed as assumptions.
- [ ] Dependencies and stakeholders are identified with role and state.
- [ ] Main flows mention happy path plus at least two edge cases (empty input, volume, concurrency, outage).
- [ ] Every Preguntas Abiertas row has question + owner role + `Abierta`; every `[SIN DEFINIR]` above has a row.
- [ ] No marketplace, comprador/vendedor, SLA, API Gateway, Okta/OAuth, owner name or date that is not in the inputs.

## How to paste it in Product Brain

1. New PRD document (base template "PRD", not a custom copy whose fields differ).
2. First message: `wow/pb/preamble.md`. Second message: "Comparto el PRD ya redactado sobre un sistema
   existente; mapealo campo por campo a la plantilla sin resumir" + the document.
   (Its prompt says shared documents are mapped into fields in the same response and forbids summarising.)
3. If the agent insists on Phase 1 Discovery, answer its summary with "dale" so it moves to Phase 2.
4. Read the backend line `**Completitud del documento:** N% · Pendiente: …` (authoritative, not the
   LLM's claim) and answer only the listed fields from the context pack.
5. Copy the full chat to `wow/pb/chats/prd.md` and run `wow pbchat audit prd --deep`.
