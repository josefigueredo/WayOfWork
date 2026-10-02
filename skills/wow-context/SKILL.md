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
3. List owner decisions in `pending-owner.md` as `- [ ] <decision>`; the user marks them `[x]`.
4. Run `wow context check` until it exits 0.
5. Verify the facts with an independent reviewer:
   `wow review --set claims --ref facts --doc wow/context-pack/facts.md --repo <repo>`.

## Rules

- A claim without a source is [SIN DEFINIR] or it is removed.
- Measured numbers keep their measurement context (where, when, how).
