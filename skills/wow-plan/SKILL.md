---
name: wow-plan
description: Turn an initiative into a Brief and an upstream kanban (epics, tasks with acceptance criteria, estimates, priority, labels) in wow/plan/, ready for readiness review and Product Brain packets. Use when starting an initiative, when the user says "plan this", or when wow-guide recommends wow-plan.
---

# wow-plan

## Steps

1. Run `wow plan guard`. Exit 1 means the manifest is frozen: stop and explain the scope-change path
   (Product Brain Artifact Engine + /spec-kit.amend). Exit 2 means there is no manifest yet:
   run `wow plan init <NNNN-name> --title "<title>" --mode greenfield|brownfield`
   (brownfield = change to an existing system; it changes phase 0 and the packet prompts).
2. Clarify with the user ONE question at a time (use a brainstorming skill if the host has one).
   Record answers in `wow/plan/PLAN.md` under `## Brief` as bullets:
   `- Goal:`, `- Decisions: D1 … · D2 …`, `- Constraints:`, `- Non-goals:`, `- Open questions:`.
   Owner decisions you cannot get go to Open questions; never invent them.
3. Do not decompose while a blocking open question remains.
4. Edit `wow/plan/manifest.json`. Each task becomes one Product Brain story, each subtask one Product Brain task:
   - epics: `done_when` ("E1.C1: …") and `product` (objective, problem, dates YYYY-MM-DD, quarter Q4/2026,
     criticality/priority Alta|Media|Baja, owner, insights…);
   - tasks: `acceptance` in Gherkin ("AC1: Dado … Cuando … Entonces …"), `component` (FE|BE|BO|QA|DEVOPS|INFRA|BFF|AI),
     `story` (user_story_text "Como … quiero … para …", context_and_need, scope, out_of_scope, business_rules,
     edge_cases, assets, technical_info), `estimate` in Fibonacci (1, 2, 3, 5, 8, 13), `priority` (high|medium|low),
     `labels`, `depends_on`;
   - subtasks: a string, or `{"title", "purpose", "how_to", "component"}`.
5. Run `wow manifest validate`, `wow manifest lint` and `wow manifest lint --pb` until all exit 0.
6. Hand off to readiness: `wow review --set readiness --ref plan`. Never set `plan.readiness` yourself.

## Rules

- Acceptance criteria must be verifiable; vague ones fail readiness R1.
- Keep task ids stable once packets exist: renaming breaks the AC anchors used in later reviews.
