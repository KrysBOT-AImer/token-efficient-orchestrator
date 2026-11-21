---
name: orchestrator-planner
description: >-
  Dedicated Stage 1A/1B planning and 3-layer Kanban materialization protocol for @planner
  (implementation_plan.md, kanban/board.md, and self-contained kanban/WP-XX_<slug>.md cards)
  under the v2.0.0 Three-Family Model Matrix. Load ONLY as @planner.
---

# Dedicated `@planner` Protocol (v2.0.0 — Two-Stage 3-Layer Kanban)

This skill is **exclusively for `@planner`** (spawned on `gemini-4-neon-high` for multi-WP Mode B/C, `gemini-4-neon-medium` for single-WP Mode A / minor revisions, or `gemini-4-carbon-high` for formal/crypto/consensus invariants). Non-planner workers and Phase 0 scouts must NOT load this file.

`@planner` holds **exclusive write authority** (enforced by `orchestrator_guard.py`) over:
- `<parentArtifactDirectoryPath>/implementation_plan.md`
- `<parentArtifactDirectoryPath>/kanban/**`

---

## Stage 1A — Lean Human Control Plan (`implementation_plan.md`)

In Stage 1A, write **ONLY** `<parentArtifactDirectoryPath>/implementation_plan.md`. Do **NOT** create `kanban/` files or cards yet (lazy materialization saves tokens if the user requests plan revisions).

### Artifact Metadata & Contract
- Use `ArtifactMetadata`: `{RequestFeedback: true, UserFacing: true, Summary: "<concise 1-2 line summary>"}`.
- Read `<parentArtifactDirectoryPath>/scratch/brainstorm_notes.md` if Phase 0.5 Brainstorming was run.
- Keep `implementation_plan.md` as a **lean human-control overview** with exactly **4 sections**:

```markdown
# Implementation Plan: <Task Title>

## 1. Reconnaissance & Alignment Summary
- Key Phase 0 findings (verified paths, symbols, constraints).
- Alignment decisions from Phase 0.5 (reference `scratch/brainstorm_notes.md` if present).

## 2. Goal & High-Level Proposed Changes
- Product/architectural changes grouped by component or module.
- NOTE: Human-facing architectural view ONLY — NO worker splits, NO model routing tables, NO raw code payloads.

## 3. Risks, Trade-Offs & Non-Goals
- Explicit non-goals and scope boundaries.
- Key technical risks and mitigations.

## 4. High-Level Verification Criteria
- End-to-end tests, build/lint checks, and observable acceptance criteria.
```

### Stage 1A Hand-Off & Revision Loop
1. After writing `implementation_plan.md`, post:
   `@coordinator STATUS: PLAN_READY - <2-sentence summary of the plan>`
2. Immediately call `swarm_wait(since=<last_seq>)` to enter zero-token sleep.
3. **Revision Loop**: If the user requests changes before approval, `@coordinator` wakes you with `post_message("@planner ...")`. Edit `<parentArtifactDirectoryPath>/implementation_plan.md` in-place, post `@coordinator STATUS: PLAN_READY - <updated 2-sentence summary>`, and return to `swarm_wait()`.

---

## Stage 1B — Lazy 3-Layer Kanban Materialization (Post-Approval)

Upon user approval, `@coordinator` wakes you (reusing your warm KV cache) with `Plan approved. Materialize kanban/board.md and kanban/WP-*.md cards.`

All `kanban/` artifacts MUST use:
`ArtifactMetadata: {RequestFeedback: false, UserFacing: false, Summary: "<concise summary>"}`

### 1. Valid v2.0.0 Model Tiers for Board Assignment
Assign **only** valid v2.0.0 model tiers (NEVER assign `xhigh` modes or `Orchestrator (Neon)/(Carbon)`):

| Role / Mode | Default Model Tier | Selective Promotion / Fallback |
| :--- | :--- | :--- |
| **Mode C Author (`workspace="share"`)** | `gemini-4-hydrogen-medium` | `gemini-4-hydrogen-high` (complex state machines, parsers, migrations, concurrency) |
| **Mode C Verifier (`workspace="inherit"`)** | `gemini-4-hydrogen-high` | `gemini-4-hydrogen-medium` (only if `< 15%` Survival quota) |
| **Mode B `run_workflow`** | `gemini-4-hydrogen-medium` (`flash`) | `gemini-4-hydrogen-low` (grep/JSON) or `gemini-4-hydrogen-high` (AST/types) |
| **Mode A `invoke_subagent(self)`** | `flash` (`gemini-4-hydrogen-medium`) | `inherit` (only when Main Session family is needed) |
| **`@auditor` (Strict Gate)** | `gemini-4-carbon-high` | **ONLY** for `> 3` WPs or security/compliance tasks (NEVER for routine `<= 3` WP tasks) |

### 2. Layer 2: `kanban/board.md` (Orchestrator Dispatch Index)
Main Session reads **ONLY `kanban/board.md`** to dispatch Phase 2. Design waves, DAG dependencies, and **strictly disjoint file ownership** so parallel `workspace="share"` Authors never touch the same file:

```markdown
# Execution Board

## Wave & DAG Overview
- **Wave 1** (Parallel): `WP-01`, `WP-02`
- **Wave 2** (Depends on Wave 1): `WP-03`

| Wave | Card ID | Card File | Mode | Model Tier | Workspace | Disjoint Owned Files | 1-Line Dispatch Trigger | Depends On |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Wave 1 | WP-01 | `kanban/WP-01_core.md` | Mode C | `gemini-4-hydrogen-medium` | `share` | `src/core.py` | Implement core module | — |
| Wave 1 | WP-02 | `kanban/WP-02_tests.md` | Mode C | `gemini-4-hydrogen-medium` | `share` | `tests/test_core.py` | Add unit tests for core | — |
| Wave 2 | WP-03 | `kanban/WP-03_verify.md` | Mode C | `gemini-4-hydrogen-high` | `inherit` | — (Read-Only Verifier) | Verify Wave 1 changes | WP-01, WP-02 |

## Final Verification Gate
- `<exact end-to-end command(s) to run after all waves complete and branches merge>`
```

**Disjoint File Ownership Rules**:
- Two parallel Authors in the same Wave MUST NEVER own the same file.
- If a shared manifest or index file must be updated after parallel WPs, place that update in a downstream Wave (e.g., Wave 2) or assign it to a single WP.
- Include an explicit **Final Verification Gate** at the bottom of `kanban/board.md`.

### 3. Layer 3: `kanban/WP-XX_<slug>.md` (Self-Contained Worker Cards)
Each worker reads **ONLY its assigned card** (never `implementation_plan.md` or other cards). Make every card 100% self-contained:

```markdown
# WP-XX: <Concise Title>

- **Objective**: <1–2 sentences stating exact deliverable>
- **Out of Scope**: <Explicit list of files/modules/behaviors this worker MUST NOT touch>

## Target Files & Symbols
1. `path/to/file.py` (`SymbolName`, L10–L80)

## Technical Specs, Contracts & Pitfalls
- <Exact function signatures, schemas, invariants, edge cases, and references to `scratch/brainstorm_notes.md` if needed>

## Verification Commands
```bash
<exact commands the worker must run after editing>
```

## Reporting Contract
End your turn with `STATUS: COMPLETED`, `STATUS: CLARIFICATION_NEEDED`, or `STATUS: ESCALATE_REQUIRED` (under 2,500 chars).
```

### 4. Stage 1B Hand-Off
1. Verify all `WP-XX` files exist, file ownership is disjoint per wave, and no banned models (`xhigh`, `Orchestrator`) appear in `board.md`.
2. Post:
   `@coordinator STATUS: KANBAN_READY - <N waves, M cards, key dependencies>`
3. Call `swarm_wait(since=<last_seq>)` immediately to return to zero-token sleep.
