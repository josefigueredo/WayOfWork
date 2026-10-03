# WayOfWork

Skills atómicas y un CLI (`wow`) para trabajar con Product Brain, Spec-Kit y modelos fuertes
(Claude, Codex) sin perder la telemetría de Spec-Kit ni gastar de más el pool de Cursor.

Diseño: `docs/superpowers/specs/2026-10-01-wayofwork-design.md`.

## Instalación

```bash
./install.sh                      # enlaza wow/wow en ~/.local/bin/wow
npx skills add <repo> --skill wow-guide
```

Requiere Python 3.9 o superior. No instala dependencias.

## Uso

Desde la raíz del repo padre de Spec-Kit:

```bash
wow snapshot      # escribe wow/progress.json y muestra bloqueos y próximos pasos
wow state         # el estado completo en JSON, sin escribir nada
wow manifest validate | lint
wow plan init 0001-mi-iniciativa --title "Mi iniciativa"
wow plan freeze --epics E1=IRIS-40   # sumar épicas después es válido; cambiar una key ya registrada pide --reopen "<motivo>"
wow review --set story --ref IRIS-41 --repo ../backend-api   # review independiente anclado (Codex)
wow usage                                                   # consumo por marca y modelo
wow sk status | wow sk cmd plan --feature specs/001-x       # preparar pasos de Spec-Kit
wow context scan | wow context check                        # context pack con afirmaciones etiquetadas
wow context restore                                         # reponer el discovery verificado si Spec-Kit lo pisó
wow pack prd | wow pack rfc | wow pack epic --id E1         # paquetes para Product Brain
wow pbchat audit prd --deep                                 # auditar la copia del chat de PB
wow plan guard                                              # ¿se puede editar el manifiesto?
wow plan init 0001-x --title "X" --mode brownfield         # el modo cambia la fase 0 y los prompts
wow manifest lint --pb                                      # lo que Product Brain exige por historia
wow pack check prd | wow pack check epic --id E1           # predicción local del % de Product Brain
wow close --epic E1 [--apply]                               # cerrar subtareas y épica en Jira tras la review aprobada
```

Product Brain registra el trabajo; no lo planifica. Por eso `wow pack prd` y `wow pack rfc` generan **paquetes de
registro**: la forma exacta de la plantilla de Product Brain, con contenido real donde el plan orienta la épica (Goal,
Problem, Contexto, Constraints, Non-goals, Decisions y criterios de cierre) y `No aplica: …` en el resto. Salen al 100%
sin nada que completar. `--full` (deprecado) deja `{{campo}}` para llenarlos con los prompts de
`skills/wow-pack/references/`.

`wow pack check` predice el porcentaje que va a marcar Product Brain con sus mismas reglas
(`reference/product-brain/README.md`) y falla con lo que Product Brain rompe o filtra a Jira: ids del context pack
(C14, D2), sufijos "(tarea x.y)", ítems de lista con comas y bloques de API más allá de A, B y C.

## Dashboard

Abrí `dashboard/wow-dashboard.html` en el navegador y arrastrá uno o varios `wow/progress.json`
(los genera `wow snapshot`). No usa red: una Content-Security-Policy bloquea toda conexión saliente.
Con varios archivos aparece la vista de portfolio. En `dashboard/examples/` hay tres snapshots de ejemplo.

Para un resumen que se comparte como un solo archivo, `wow dashboard --out resumen.html --project <ruta>`
(repetí `--project` para un portfolio) refresca los snapshots y los deja embebidos: el HTML abre offline,
sin arrastrar nada.

Con `--backfill-git` (en `wow snapshot` y `wow dashboard`), la historia suma un punto por cada commit que tocó
`specs/*/tasks.md`: velocity muestra el burn-up real aunque el primer snapshot llegue con la épica terminada.

## Consumo de Cursor

`wow hook install-cursor` agrega a `~/.cursor/hooks.json` un hook `stop` que guarda, por cada turno del agente,
modelo y tokens en `harness/cursor-turns/` del repo que tenga `wow/`. Corre al lado del hook de telemetría de
Spec-Kit sin cambiar lo que envía a New Relic, y no guarda el email ni la ruta del transcript.
`wow usage` y `wow snapshot` leen esos turnos. Las revisiones de Codex quedan en `harness/reviews/`.

Para ver costos estimados, cargá una tabla de precios (USD por millón de tokens) en `.wow/config.json`:

```json
{"pricing": {"as_of": "2026-10-01", "per_mtok": {"claude-opus-5-5": {"in": 15, "out": 75, "cache_read": 1.5, "cache_write": 18.75}}}}
```

Credenciales de Jira: variables `IC_JIRA_BASE_URL`, `IC_JIRA_USER_EMAIL`, `IC_JIRA_API_TOKEN`
(opcionales: `IC_JIRA_PROJECT_KEY`, `IC_JIRA_EPIC_CHILD_MODE`). Se leen del shell, de `.env.local`
o, como último recurso, de `JIRA_*` en `.spec-kit/.env`. `wow` nunca las imprime.

**Deprecado:** `wow run-wu` (cursor-agent headless; las WUs se corren en el chat de Cursor y el hook `stop` mide el
consumo) y `wow pack prd|rfc --full` (los paquetes de registro salen completos). Siguen funcionando y avisan por stderr.

Códigos de salida: `0` OK · `1` hallazgos · `2` no pude evaluar.

## Tests

```bash
python3 -m unittest discover -s tests -v
/usr/bin/python3 -m unittest discover -s tests -v   # verifica compatibilidad con 3.9
```
