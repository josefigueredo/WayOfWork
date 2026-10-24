---
name: wow-guide
description: Tell the operator where the two WayOfWork flows stand (Product Brain and Spec-Kit, joined only by a Jira epic key) and what to do next — each flow's checklist with its percent complete, blockers, and up to three next steps with where to run them, which model and the exact command. Use when the user asks "what's next", "where am I", "qué sigue", or opens a work session.
compatibility: Requires the `wow` CLI on PATH (./install.sh in the WayOfWork repo; Python 3.9+ and git). Jira status needs JIRA_BASE_URL, JIRA_EMAIL and JIRA_API_TOKEN, otherwise it reports Jira as not configured.
---

# wow-guide

Read-only navigator. It never executes the steps it recommends.

## When to use

- The user asks what to do next, where the work stands, or starts a session.
- After any step finishes, to confirm the phase advanced.

## The two flows

- **Flujo PB** (Product Brain): context, plan, packets, PRD/RFC/epic chats and their audits, export to Jira, field
  repair. It ends when each epic is in Jira with all its stories.
- **Flujo SK** (Spec-Kit), one per Jira epic key: discovery, sync, clarify, plan, tasks, work units, story reviews,
  stories Done (sync-status, in Cursor), epic review and close. The key may come from Product Brain's export, from
  jtk, or from an epic made anywhere else that wow-sk-prep registers. What Product Brain still lacks never holds it back;
  only a human-rejected audit does.

## Steps

1. From the project root (the Spec-Kit parent repo), run `wow progress`. It rewrites `wow/checklists/pb.md` and
   one `wow/checklists/sk-<KEY>.md` per epic, prints each flow with its percent and what is left, and refreshes
   the statusline summary. A `[?]` item could not be verified (Jira down, no log): it never counts as done.
2. Run `wow snapshot` for blockers and next steps (it writes `wow/progress.json`), or `wow state` for the full JSON
   without writing anything.
3. Explain the result to the user, one flow at a time ("Flujo PB" first, then each "Flujo SK · <KEY>"):
   - Blockers first (owner decisions). They are human tasks, never resolve them by inference.
   - Then up to three next steps, each with: action, **where** (`harness`, `product-brain`,
     `cursor`), model, exact command, and the `why` field.
   A step with `recommended: true` is optional: say so, it never holds a phase open.
   - Point out any epic whose phase is `unknown` and quote its `reason` verbatim.
   - Mention `sources` that are not `ok`.
   - Name any manual checklist item ticked without evidence (`wow progress` prints them): it does not count.
4. Let the user choose the next step: if the host has a multiple-choice question tool (Claude Code: AskUserQuestion), use it: single-select, recommended option first and marked "(Recomendado)", the tradeoff in each option's description, up to 4 options and 4 questions per call. Otherwise, numbered options in text.
   Options: up to three next steps (label = the action in ≤5 words; description = where + why) plus
   "Explicame el estado". Then stop, and run only the step the user picked.

## Rules

- Measure, do not speculate: a value you can measure (a count, a time, a commit, a URL, a status) is measured before you state it, and cited. Every repo, branch, commit or URL you hand out must exist and be reachable on the remote's default branch: check it before handing it out. What cannot be measured is labelled as an inference and never presented as a cause.
- IDs defined earlier in the conversation (E1, D10, C14, AC1, WU-005, US-001) get a few-word gloss the first time each message mentions them, e.g. "E2 (cifras del motor al día)": the user must not have to scroll back to know what they are.
- Do not infer phases from prose: the JSON is the source of truth.
- Never invent a step that is not in `next_steps`; if the list is empty and every epic is `done`,
  say the plan is complete.
- `cursor` steps spend the scarce Cursor pool: say so and suggest batching them. wow-sk-prep can send them to Cursor from
  here, except `/spec-kit.sync-status`, which the user runs in Cursor.
- Never tick a derived checklist item by hand: change the evidence (the file, the review, Jira) and rerun.
- Exit code 2 means wow could not evaluate (for example an invalid `.wow/config.json`);
  report the message, do not guess.
