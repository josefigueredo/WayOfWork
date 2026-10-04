# WayOfWork: instrucciones para agentes

Este repo es `wow` (CLI en Python stdlib 3.9+) y las 7 skills `wow-*`. Lo usan Claude Code y Codex para llevar una
iniciativa por Product Brain (registro), Spec-Kit (ejecución en Cursor) y Jira, con revisión independiente.

## Instalar en una máquina nueva

1. El repo no tiene remoto por ahora: llega como copia (con su `.git`). Desde su raíz, correr `./install.sh --skills`. Si sale con 1, informá qué directorio bloqueó y no lo borres.
2. Verificar con `wow --version`. Si no está en el PATH, agregá `~/.local/bin`.
3. Correr `wow hook install-cursor` (una vez por máquina).
4. Revisar los requisitos de la tabla del README. Pedile al usuario lo que falte, sin instalar credenciales por tu cuenta.
   Las de Jira van en el shell o en `.env.local` como `IC_JIRA_*`, y nunca se imprimen ni se commitean.

## Usar

- Empezá siempre por la skill `wow-guide` (o `wow state`): devuelve la fase, los bloqueos y a lo sumo 3 pasos con dónde
  hacerlos. No infieras el estado leyendo archivos a mano.
- Las skills no se encadenan: cada una hace un paso y vuelve a la guía.
- `wow close --apply` es la única escritura hacia afuera (transiciona issues en Jira). Mostrá primero el dry-run y pedí
  confirmación. Las historias las cierra Spec-Kit (`sync-status`), nunca `wow`.
- Para estimar, usá `wow estimate --history <épica terminada>` y decí qué números son medidos y cuáles supuestos.
  El modelo de Cursor para cada WU lo sugiere `wow state`; no lo elijas a ojo.
- **Medir, no especular.** Todo valor que se pueda medir (un conteo, un tiempo, un commit, una URL, un estado) se mide antes de afirmarlo, y se cita. Todo repo, rama, commit o URL que se entrega tiene que existir y estar en la rama por defecto del remoto: verificalo con `wow ref check`. Lo que no se puede medir se rotula como inferencia y nunca se presenta como causa.
- Códigos de salida: 0 OK · 1 hallazgos · 2 no pude evaluar.

## Desarrollar

- TDD. Suite: `python3 -m unittest discover -s tests`, también con `/usr/bin/python3` (3.9).
- Código, skills y CLI en inglés; documentación humana en castellano.
- Conventional commits, sin atribución a IA.
