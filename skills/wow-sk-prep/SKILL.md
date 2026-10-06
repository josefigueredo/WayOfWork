---
name: wow-sk-prep
description: Prepare each Spec-Kit step so Cursor only ratifies: pre-chew clarify answers and a plan draft with the host model, then send the Spec-Kit command to Cursor with `wow sk run` (an interactive cursor-agent, recorded like a typed command) or hand it to the user for Cursor. Use before /spec-kit.sync, clarify, plan, tasks or implement, or when wow-guide recommends `wow sk cmd`.
---

# wow-sk-prep

Goal: spend the scarce Cursor pool only on ratifying and generating, never on thinking.

## Steps

0. An epic that did not come from Product Brain's export (made with jk or by hand) enters the Spec-Kit flow with
   `wow sk start <KEY>`; after that wow-guide and `wow progress` follow it like any other.
1. Run `wow sk status` (add `--feature specs/<dir>` to focus). Exit 1 means import warnings or tasks
   without `jira:` keys: report them; warnings are Product Brain debt, fix them there, not in the spec.
2. Before clarify or plan, write the inputs yourself with the strongest host model:
   - `wow/sk/<feature-name>/clarify-answers.md`: answers to the ambiguities, citing the RFC and the
     manifest; mark unknowns as [SIN DEFINIR].
   - `wow/sk/<feature-name>/plan-draft.md`: the design decisions, alternatives and contracts.
3. Get the exact command with `wow sk cmd <sync|clarify|plan|tasks|sync-status> --epic <KEY> | --feature specs/<dir>`.
   Then either:
   - **send it from here:** `wow sk run "<command>"`. It drives an interactive `cursor-agent` through the
     run-in-cursor skill, so the command's start/end and every Cursor hook (model, tokens) are recorded as if typed.
     It returns when the turn ends and prints Cursor's screen: show it. If Cursor asks something (clarify does),
     answer with `wow sk send <session> "<reply>"`, asking the user when the answer is theirs. Always finish with
     `wow sk quit <session>`. Exit 124 is a timeout: the session is still alive (`tmux attach -t <session>`).
   - **or hand it to the user** for the IDE chat or `cursor-agent` without `-p`, when they prefer to run it there.
   `/spec-kit.sync-status` always goes to the user: it writes to Jira, and wow and the guardrail refuse to send it.
   Never `cursor-agent -p` (it runs the command but fires no `stop`, so turns and tokens are lost) nor the
   `spec-kit` terminal CLI (it sends no telemetry).
4. For implementation, send or hand `/spec-kit.implement <WU-ID>` with the model wow-guide
   suggests for that unit (Product Brain and Spec-Kit suggest none; `wow estimate` lists them all). Its tokens are recorded
   per turn in `harness/cursor-turns/` once `wow hook install-cursor` ran (once per machine).

## Rules

- Measure, do not speculate: a value you can measure (a count, a time, a commit, a URL, a status) is measured before you state it, and cited. Every repo, branch, commit or URL you hand out must exist and be reachable on the remote's default branch: check it (`wow ref check`). What cannot be measured is labelled as an inference and never presented as a cause.
- IDs defined earlier in the conversation (E1, D10, C14, AC1, WU-005, US-001) get a few-word gloss the first time each message mentions them, e.g. "E2 (cifras del motor al día)": the user must not have to scroll back to know what they are.
- Never replace a `/spec-kit.*` command with your own implementation: telemetry must see it.
- Escalate a work unit to a stronger Cursor model after its third NEEDS_REVISION, not before.
- `wow run-wu` (headless cursor-agent) is deprecated: the pilot ran every work unit in interactive Cursor.
