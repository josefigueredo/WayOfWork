---
name: wow-plan
description: Turn an initiative into a Brief and an upstream kanban (epics, tasks with acceptance criteria, estimates, priority, labels) in wow/plan/, ready for readiness review and Product Brain packets. Use when starting an initiative, when the user says "plan this", or when wow-guide recommends wow-plan.
compatibility: Requires the `wow` CLI on PATH (./install.sh in the WayOfWork repo; Python 3.9+ and git).
---

# wow-plan

## Steps

1. Run `wow plan guard`. Exit 1 means the manifest is frozen: stop and explain the scope-change path, which is manual
   and in this order: the PRD in Product Brain, then the RFC and epic there (each step rereads the earlier documents but
   does not update itself), then the Jira stories by hand (never re-export: it duplicates issues), then
   `/spec-kit.amend`; if a registered key changed, `wow plan freeze --reopen "<reason>"`. Exit 2 means there is no manifest yet:
   run `wow plan init <NNNN-name> --title "<title>" --mode greenfield|brownfield`
   (brownfield = change to an existing system; it changes phase 0 and where Spec-Kit discovery fits).
2. Clarify with the user ONE question at a time (use a brainstorming skill if the host has one). For a decision
   with 2-4 discrete alternatives, if the host has a multiple-choice question tool (Claude Code: AskUserQuestion), use it: single-select, recommended option first and marked "(Recomendado)", the tradeoff in each option's description, up to 4 options and 4 questions per call. Otherwise, numbered options in text.
   Record answers in `wow/plan/PLAN.md` under `## Brief` as bullets:
   `- Goal:`, `- Problem:`, `- Decisions: D1 … · D2 …`, `- Constraints:`, `- Non-goals:`, `- Open questions:`,
   plus a `## Contexto` paragraph. These are what the Product Brain packets carry; everything else is marked
   "No aplica". Owner decisions you cannot get go to Open questions; never invent them.
3. Do not decompose while a blocking open question remains. If the user lets a decision ride on a default that the
   plan carries as a task, mark it `- [~] <decision> → plan: <task>` in `pending-owner.md`: it no longer blocks.
4. Edit `wow/plan/manifest.json`. Each task becomes one Product Brain story, each subtask one Product Brain task:
   - epics: `done_when` ("E1.C1: …") and `product` (objective, problem, dates YYYY-MM-DD, quarter Q4/2026,
     criticality/priority Alta|Media|Baja, owner, insights…); `status: "draft"` parks an epic: `wow state` asks for
     no packet or Product Brain step for it until it is `active` (the default);
   - when the project has a documentation site, every epic carries a subtask that re-documents it (pages to update
     named in `how_to`): keeping docs current is part of each epic, not a scheduled check;
   - tasks: `acceptance` in Gherkin ("AC1: Dado … Cuando … Entonces …"), `component` (FE|BE|BO|QA|DEVOPS|INFRA|BFF|AI),
     `story` (user_story_text "Como … quiero … para …", context_and_need, scope, out_of_scope, business_rules,
     edge_cases, assets, technical_info), `estimate` in Fibonacci (1, 2, 3, 5, 8, 13), `priority` (high|medium|low),
     `labels`, `depends_on`;
   - subtasks: a string, or `{"title", "purpose", "how_to", "component"}`.
5. Run `wow manifest validate`, `wow manifest lint` and `wow manifest lint --pb` until all exit 0.
6. Estimate with `wow estimate --history <a finished epic's project>`: give the user the range and end date it prints,
   saying which numbers are measured and which are assumed. A task can pin a Cursor model with `model`.
7. Hand off to readiness: `wow review --set readiness --ref plan`. Never set `plan.readiness` yourself.

## Rules

- Measure, do not speculate: a value you can measure (a count, a time, a commit, a URL, a status) is measured before you state it, and cited. Every repo, branch, commit or URL you hand out must exist and be reachable on the remote's default branch: check it (`wow ref check`). What cannot be measured is labelled as an inference and never presented as a cause.
- IDs defined earlier in the conversation (E1, D10, C14, AC1, WU-005, US-001) get a few-word gloss the first time each message mentions them, e.g. "E2 (cifras del motor al día)": the user must not have to scroll back to know what they are.
- Acceptance criteria must be verifiable; vague ones fail readiness R1.
- Keep task ids stable once packets exist: renaming breaks the AC anchors used in later reviews.
