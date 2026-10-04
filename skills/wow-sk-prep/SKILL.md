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
3. Print the exact command with `wow sk cmd <sync|clarify|plan|tasks|sync-status> --epic <KEY> | --feature specs/<dir>`
   and hand it to the user to paste in the Cursor chat. Never suggest the `spec-kit` terminal CLI or headless
   `cursor-agent` instead: only the chat fires the token hooks and the command's start/end telemetry.
4. For implementation, hand the user `/spec-kit.implement <WU-ID>` for the Cursor chat with the model wow-guide
   suggests for that unit (Product Brain and Spec-Kit suggest none; `wow estimate` lists them all). Its tokens are recorded
   per turn in `harness/cursor-turns/` once `wow hook install-cursor` ran (once per machine).

## Rules

- Measure, do not speculate: a value you can measure (a count, a time, a commit, a URL, a status) is measured before you state it, and cited. Every repo, branch, commit or URL you hand out must exist and be reachable on the remote's default branch: check it (`wow ref check`). What cannot be measured is labelled as an inference and never presented as a cause.
- IDs defined earlier in the conversation (E1, D10, C14, AC1, WU-005, US-001) get a few-word gloss the first time each message mentions them, e.g. "E2 (cifras del motor al día)": the user must not have to scroll back to know what they are.
- Never replace a `/spec-kit.*` command with your own implementation: telemetry must see it.
- Escalate a work unit to a stronger Cursor model after its third NEEDS_REVISION, not before.
- `wow run-wu` (headless cursor-agent) is deprecated: the pilot ran every work unit in the Cursor chat.
