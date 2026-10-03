---
name: wow-guide
description: Tell the operator what to do next in the WayOfWork flow (Product Brain + Spec-Kit + strong models): current phase per plan and epic, blockers, and up to three next steps with where to run them, which model and the exact command. Use when the user asks "what's next", "where am I", "qué sigue", or opens a work session.
---

# wow-guide

Read-only navigator. It never executes the steps it recommends.

## When to use

- The user asks what to do next, where the work stands, or starts a session.
- After any step finishes, to confirm the phase advanced.

## Steps

1. From the project root (the Spec-Kit parent repo), run `wow snapshot`.
   It writes `wow/progress.json` and prints blockers and next steps.
2. If you need the full state without writing anything, run `wow state` (JSON on stdout).
3. Explain the result to the user:
   - Blockers first (owner decisions). They are human tasks, never resolve them by inference.
   - Then up to three next steps, each with: action, **where** (`harness`, `product-brain`,
     `terminal`, `cursor`), model, exact command, and the `why` field.
   A step with `recommended: true` is optional: say so, it never holds a phase open.
   - Point out any epic whose phase is `unknown` and quote its `reason` verbatim.
   - Mention `sources` that are not `ok`.
4. Stop. Do not run the recommended commands unless the user asks for that specific step.

## Rules

- Do not infer phases from prose: the JSON is the source of truth.
- Never invent a step that is not in `next_steps`; if the list is empty and every epic is `done`,
  say the plan is complete.
- `cursor` steps spend the scarce Cursor pool: say so and suggest batching them.
- Exit code 2 means wow could not evaluate (for example an invalid `.wow/config.json`);
  report the message, do not guess.
