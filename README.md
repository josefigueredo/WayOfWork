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
wow run-wu WU-008 --epic E1                                 # implementar una WU midiendo el consumo
wow context scan | wow context check                        # context pack con afirmaciones etiquetadas
wow pack prd | wow pack rfc | wow pack epic --id E1         # paquetes para Product Brain
wow pbchat audit prd --deep                                 # auditar la copia del chat de PB
wow plan guard                                              # ¿se puede editar el manifiesto?
```

Credenciales de Jira: variables `IC_JIRA_BASE_URL`, `IC_JIRA_USER_EMAIL`, `IC_JIRA_API_TOKEN`
(opcionales: `IC_JIRA_PROJECT_KEY`, `IC_JIRA_EPIC_CHILD_MODE`). Se leen del shell, de `.env.local`
o, como último recurso, de `JIRA_*` en `.spec-kit/.env`. `wow` nunca las imprime.

Códigos de salida: `0` OK · `1` hallazgos · `2` no pude evaluar.

## Tests

```bash
python3 -m unittest discover -s tests -v
/usr/bin/python3 -m unittest discover -s tests -v   # verifica compatibilidad con 3.9
```
