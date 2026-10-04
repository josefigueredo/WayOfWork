---
name: wow-context
description: Build the context pack (facts, metrics, decisions, contracts, owner decisions) from the real repositories, with every claim tagged and sourced, then verify it with an independent reviewer. Use at the start of an initiative, when the repo changed, or when wow-guide recommends wow-context.
---

# wow-context

## Steps

1. Run `wow context scan`: it inventories child repos and docs into `wow/context-pack/inventory.md`
   and creates missing skeleton files.
2. Read the code and docs it lists. Write claims, one per line, in facts.md, metrics.md,
   decisions.md and contracts.md:
   `- C<n>: <claim> [MEDIDO|ESTIMACIÓN|SIN DEFINIR] (fuente: path:line)`.
   - brownfield (plan.mode): architecture claims cite `.spec-kit/discovery/architecture.md` (from
     /spec-kit.discovery) or the code; baselines are [MEDIDO] with where, when and how.
   - greenfield: keep discovery notes (interviews, benchmarks, exports) in the repo and cite them; most numbers
     are [ESTIMACIÓN] or [SIN DEFINIR] until launch.
3. brownfield: Spec-Kit's discovery needs corrections (the pilot found 9). Check `.spec-kit/discovery/*.md` and
   `local-constitution.md` against the code yourself, fix them in place, and keep the verified copies plus an
   `ERRATA.md` (said / correction / evidence) in `wow/context-pack/discovery/`. From then on `wow context check`
   fails if a new /spec-kit.discovery overwrites them, and `wow context restore` puts them back.
4. List owner decisions in `pending-owner.md` as `- [ ] <decision>`; the user marks them `[x]`. When you ask them,
   group them in blocks and, for those with discrete alternatives, if the host has a multiple-choice question tool (Claude Code: AskUserQuestion), use it: single-select, recommended option first and marked "(Recomendado)", the tradeoff in each option's description, up to 4 options and 4 questions per call. Otherwise, numbered options in text.
5. Run `wow context check` until it exits 0: every `fuente: path:line` must exist and be in range.
   For any other document that cites code (an audit report, a design doc), run
   `wow cite check <doc> --root <repo> [--sha <commit>]`: deterministic, so it does not depend on the reviewer.
6. Verify the facts with an independent reviewer:
   `wow review --set claims --ref facts --doc wow/context-pack/facts.md --repo <repo>`.

## Rules

- IDs defined earlier in the conversation (E1, D10, C14, AC1, WU-005, US-001) get a few-word gloss the first time each message mentions them, e.g. "E2 (cifras del motor al día)": the user must not have to scroll back to know what they are.
- A claim without a source is [SIN DEFINIR] or it is removed.
- Measured numbers keep their measurement context (where, when, how).
