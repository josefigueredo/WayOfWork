# WayOfWork

Skills atómicas y un CLI (`wow`) para trabajar con Product Brain, Spec-Kit y modelos fuertes
(Claude, Codex) sin perder la telemetría de Spec-Kit ni gastar de más el pool de Cursor.

Diseño: `docs/superpowers/specs/2026-10-01-wayofwork-design.md`.

## Instalación

```bash
cd <ruta>/WayOfWork          # sin remoto por ahora: copiá el repo con su .git (zip o rsync)
./install.sh --skills     # CLI en ~/.local/bin/wow + las 7 skills wow-* para Claude Code y Codex
wow --version             # si falla, agregá ~/.local/bin al PATH
wow hook install-cursor   # una vez por máquina: mide modelo y tokens de cada turno de Cursor (chat o cursor-agent interactivo)
```

`install.sh` solo crea symlinks hacia este repo, así que un `git pull` actualiza CLI y skills sin reinstalar. Las skills
siguen el layout compartido: `~/.agents/skills/wow-*` apunta al repo, y `~/.claude/skills/wow-*` y
`~/.codex/skills/wow-*` apuntan a `../../.agents/skills/wow-*`. Re-correrlo es seguro, y nunca reemplaza un directorio real
con el mismo nombre: en ese caso sale con código 1 y dice cuál es. `--bin-dir DIR` instala el CLI en otro directorio.

### Requisitos

| Qué | Para qué | Si falta |
|---|---|---|
| Python 3.9+ y git | todo `wow`; no instala dependencias | no corre |
| Spec-Kit (`uv tool install git+ssh://git@github.com/josefigueredo/spec-kit.git`) y Cursor | fases 4 a 6 | la guía se queda en la fase 3 |
| CLI de Codex (o Copilot) logueado | revisor independiente de `wow review` y `wow pbchat audit --deep` | `wow review` sale con 2 (no pude evaluar) |
| `gh` logueado | links a PRs en el snapshot y el dashboard | el snapshot marca GitHub como no disponible |
| Token de Jira **sin scopes** (`IC_JIRA_*`, ver abajo) | estado de las épicas y `wow close` | Jira figura como no configurado |

Un token de Jira con scopes responde 401 contra `https://<sitio>.atlassian.net` y Jira contesta como anónimo, así que
parece falta de permisos. La prueba que separa los dos casos es `GET /rest/api/3/myself`.

## Uso

Desde la raíz del repo padre de Spec-Kit:

```bash
wow snapshot      # escribe wow/progress.json y muestra bloqueos y próximos pasos
wow state         # el estado completo en JSON, sin escribir nada
wow manifest validate | lint
wow plan init 0001-mi-iniciativa --title "Mi iniciativa"
wow plan freeze --epics E1=IRIS-40   # sumar épicas después es válido; cambiar una key ya registrada pide --reopen "<motivo>"
wow review --set story --ref IRIS-41 --repo ../backend-api   # review independiente anclado (Codex)
wow review --set standards --ref E1 --repo ../backend-api   # segundo eje: golden rules + smells (no el spec)
wow usage                                                   # consumo por marca y modelo
wow sk status | wow sk cmd plan --feature specs/001-x       # preparar pasos de Spec-Kit
wow context scan | wow context check                        # context pack con afirmaciones etiquetadas
wow context restore                                         # reponer el discovery verificado si Spec-Kit lo pisó
wow cite check doc.md --root ../repo [--sha SHA] [--alias X=ruta]   # cada `archivo:línea` citado existe y está en rango
wow ref check doc.md                                        # cada `nombre @ sha` y URL de GitHub está en la rama por defecto del remoto
wow estimate [--history ../epica-anterior]                 # horas y fecha calibradas con épicas pasadas + modelo por tarea
wow pack prd | wow pack rfc | wow pack epic --id E1         # paquetes para Product Brain
wow pbchat audit prd --deep                                 # auditar la copia del chat de PB
wow pbchat audit rfc                                        # con solo chats/rfc.final.md: la sección para pegar en el editor de PB
wow pbchat audit prd --decide approved --reason "<por qué>"  # veredicto humano: el owner decide no corregir el documento en PB
wow jira fix-fields --epic E1 [--apply]                     # tras exportar desde PB: componente, puntos, prioridad y labels de cada historia
wow plan guard                                              # ¿se puede editar el manifiesto?
wow plan init 0001-x --title "X" --mode brownfield         # el modo cambia la fase 0 y los prompts
wow manifest lint --pb                                      # lo que Product Brain exige por historia
wow pack check prd | wow pack check epic --id E1           # predicción local del % de Product Brain
wow close --epic E1 [--subtasks] [--apply]                               # --subtasks tras cada sync-status; sin él, subtareas y épica al final
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

**Deprecado:** `wow run-wu` (`cursor-agent -p`; las WUs se corren en Cursor interactivo y el hook `stop` mide el
consumo) y `wow pack prd|rfc --full` (los paquetes de registro salen completos). Siguen funcionando y avisan por stderr.

### Lo que el export de Product Brain deja mal en Jira

Medido en PLATE-504 (piloto IRIS, código de PB en `9b19a89`):

- **Labels y prioridad:** PB copia las de la épica a todas las historias (`jira.exporter.ts:551-616`).
- **Componente:** si el proyecto de Jira no tiene ese componente, Jira rechaza el alta. PB reintenta con campos mínimos y
  después recupera solo las labels (`jira.client.ts:1236-1276`). Se pierden el componente, los puntos y la prioridad.
- **Story points:** PB los busca en el primer campo numérico de la instancia (`jira.client.ts:1342-1348`), que puede ser
  cualquiera ("Valor del Riesgo" en ese Jira).

`wow manifest lint --pb` avisa antes del export qué componentes no existen en el proyecto. `wow jira fix-fields --epic E1`
repara después: elige el campo de puntos por nombre en la pantalla de edición, nunca inventa un componente, y escribe
solo con `--apply`. Si la pantalla del tipo de issue no tiene campo de puntos (como en PLATE), lo dice: eso se arregla
en la configuración de Jira.

### Dónde correr los comandos de Spec-Kit

Medido con `cursor-agent` 2026.10.01 el 2026-10-04 (hook de sondeo sobre los eventos, más el piloto IRIS):

| Dónde | `start`/`end` del comando (SpecKitCommand) | Hook `stop`: modelo y tokens del turno (SK y `wow hook`) | ¿Sirve para registrar? |
|---|---|---|---|
| Chat de la GUI de Cursor | sí | sí | sí |
| `cursor-agent` interactivo (sin `-p`) | sí | sí (3 turnos con tokens en el piloto IRIS) | sí |
| `cursor-agent -p` | sí: expande el comando y corre sus líneas `Run:` | no: tampoco llega `beforeSubmitPrompt`; solo `sessionStart`, `postToolUse` y `sessionEnd` | no |
| CLI `spec-kit` de la terminal | no | no | no |

No medí si `beforeSubmitPrompt` llega en el modo interactivo del CLI: el piloto mide `stop`, que es el que trae los tokens.

Códigos de salida: `0` OK · `1` hallazgos · `2` no pude evaluar.

## Estimación y modelo por tarea

`wow estimate --history <proyecto de una épica terminada>` (repetible, o `estimate.history` en `.wow/config.json`)
convierte el plan en horas y fecha de fin. Cada componente dice si es **medido** o **supuesto**:

| Componente | Medido de la épica de referencia | Supuesto por defecto |
|---|---|---|
| Implementación | minutos del ledger de Spec-Kit (`feature.specified` → `feature.implemented`) por hora que estimó `tasks.shape`, o por punto de historia si todavía no hay WU | 7 min por hora estimada · 20 min por punto |
| Reviews | rondas por historia y por épica (`wow/reviews/`) × minutos entre rondas consecutivas (`harness/reviews/`), que incluyen la corrección | 2 rondas · 18 min por ronda |
| Product Brain | — (no deja rastro de tiempo) | 20 min por chat: PRD, RFC y uno por épica |
| Operación | — | 15 min por historia (PR, merge, sync-status) |

El rango es ±50% con una épica de referencia y ±30% con dos o más. La fecha cuenta días hábiles a
`estimate.hours_per_day` (4 por defecto). Todos los supuestos se cambian en `.wow/config.json` bajo `estimate`.

Product Brain y Spec-Kit no asignan modelo a las tareas, así que lo sugiere WoW: el de razonamiento
(`models.cursor_reason`) para lo grande o delicado (≥5 puntos, una WU de ≥4 h estimadas, componentes INFRA, DEVOPS o
AI, labels de arquitectura, seguridad o migración) y el de generación (`models.cursor_generate`) para el resto. Un
campo `model` en la tarea del manifiesto gana siempre. `wow state` lo pone en cada paso `/spec-kit.implement`.

## Revisiones independientes

- **Dos ejes:** `--set story|epic` revisa contra los criterios de la historia o la épica; `--set standards`, contra
  las golden rules instaladas en el repo. Se guardan por separado (`<ref>.standards`).
- **Evidencia de CI:** los paquetes de historia y épica llevan las corridas de GitHub Actions del commit de `HEAD`.
- **Un veredicto vale para el contenido que vio:** si el contenido cambia después de una aprobación (o de una
  decisión humana), `wow review` abre un ciclo nuevo y el tope de 3 rondas cuenta desde ahí.
- Cada ronda guarda tokens, modelo y duración en `harness/reviews/`.

## Limitación conocida: workspaces de varios repos

`wow context check` rechaza fuentes fuera de la raíz del proyecto y `wow context scan` solo ve repos debajo de ella.
Si la documentación vive en un repo y el código en repos hermanos, la raíz tiene que ser la carpeta que los contiene
(así se hizo en IRIS). Si esa carpeta no es un repo git, `wow/` y `specs/` quedan sin versionar y `--backfill-git`
no tiene historia. Spec-Kit tiene que inicializarse en esa misma raíz para que la guía vea la feature.

## Tests

```bash
python3 -m unittest discover -s tests -v
/usr/bin/python3 -m unittest discover -s tests -v   # verifica compatibilidad con 3.9
```
