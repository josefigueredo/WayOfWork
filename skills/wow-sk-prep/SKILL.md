---
name: wow-sk-prep
description: Prepare each Spec-Kit step so Cursor only ratifies: pre-chew clarify answers and a plan draft with the host model, print the exact Spec-Kit command for the user to run in the Cursor chat. Use before /spec-kit.sync, clarify, plan, tasks or implement, or when wow-guide recommends `wow sk cmd`.
---

# wow-sk-prep

Goal: spend the scarce Cursor pool only on ratifying and generating, never on thinking.

## Steps

1. Run `wow sk status` (add `--feature specs/<dir>` to focus). Exit 1 means import warnings or tasks
   without `jira:` keys: report them; warnings are Product Brain debt, fix them there, not in the spec.
2. Before clarify or plan, write the inputs yourself with the strongest host model:
   - `wow/sk/<feature-name>/clarify-answers.md`: answers to the ambiguities, citing the RFC and the
     manifest; mark unknowns as [SIN DEFINIR].
   - `wow/sk/<feature-name>/plan-draft.md`: the design decisions, alternatives and contracts.
3. Print the exact command with `wow sk cmd <sync|clarify|plan|tasks> --epic <KEY> | --feature specs/<dir>`
   and hand it to the user. Do not run Spec-Kit commands yourself unless asked.
4. For implementation, hand the user `/spec-kit.implement <WU-ID>` for the Cursor chat. Its tokens are recorded
   per turn in `harness/cursor-turns/` once `wow hook install-cursor` ran (once per machine).

## Rules

- Never replace a `/spec-kit.*` command with your own implementation: telemetry must see it.
- Escalate a work unit to a stronger Cursor model after its third NEEDS_REVISION, not before.
- `wow run-wu` (headless cursor-agent) is deprecated: the pilot ran every work unit in the Cursor chat.
