---
name: token-efficient-orchestrator
description: >-
  Main Session & execution playbook for the v2.0.0 Three-Family Model Matrix:
  standalone gemini-4-neon-medium Main Session Dispatcher, gemini-4-neon-high @planner & Tier-1 @councillor,
  Hydrogen (Low/Medium/High) for 80%+ Mode A/B/C Recon, Authors & Verifiers, and Carbon (Low/Medium/High)
  for Tier-2 @councillor & >3-WP/security-gated @auditor. Enforces Hybrid Role-Aware Split and bans xhigh
  and Orchestrator wrapper modes.
---

# Token-Efficient Task Orchestrator (v2.0.0 — Main Session & Execution Playbook)

This skill is the **Main Session & Execution Playbook** under Antigravity's `v2.0.0` **Hybrid Role-Aware Split**:
1. **Pillar 1 — Standalone `gemini-4-neon-medium` Main Session (Pure Dispatcher)**: Eliminates the `$0.112` cross-family `fork="coordinator"` cold prefill penalty to Neon `@planner`/`@councillor` and removes all `Orchestrator` mode-switch bugs. Direct workspace edits, `run_command`, web search, MCP calls, writes outside `<artifactDirectoryPath>/scratch/`, and direct `implementation_plan.md` or `kanban/` authoring are physically blocked by `orchestrator_guard.py`. Main Session reads `kanban/board.md` (read-only) to dispatch Phase 2.
2. **Pillar 2 — Dedicated `@planner` (`Neon`), Two-Tier `@councillor`, & Gated `@auditor`**:
   - **`@planner`**: Spawned sequentially (`swarm(action="title")` then `swarm(action="add", name="planner", model="gemini-4-neon-high", fork="coordinator", workspace="inherit", ...)` for multi-WP Mode B/C; `gemini-4-neon-medium` for single-WP Mode A / minor revisions). Holds exclusive write authority over `<parentArtifactDirectoryPath>/implementation_plan.md` (Stage 1A) and `<parentArtifactDirectoryPath>/kanban/**` (Stage 1B). `@planner` loads `skills/orchestrator-planner/SKILL.md` for full schemas.
   - **Tier-1 `@councillor` (`Neon`)**: Spawned on `retry_streak >= 2` with `model="gemini-4-neon-high"`, `fork="coordinator"`, `workspace="inherit"`. Strictly **Read-Only** (enforced by `orchestrator_guard.py`).
   - **Tier-2 `@councillor` (`Carbon`) & Gated `@auditor`**: Upgrade `@councillor` in-place via `swarm(action="model", name="councillor", model="gemini-4-carbon-high")` ONLY when Tier-1 Neon fails to resolve a deadlock (saves `$0.532` / `29.9%` vs cold Carbon spawn). Spawn `@auditor` (`gemini-4-carbon-high`) strictly for **`> 3` WPs or security/compliance** tasks (NEVER for routine `<= 3` WP tasks).
3. **Pillar 3 — 80%+ Hydrogen Execution Fleet (Asymmetric Mode C Primary)**:
   - **Mode C (`swarm`)**: **Primary** for multi-file/multi-step coding: **`gemini-4-hydrogen-medium`** Authors (`workspace="share"`, selective `high` for complex algorithmic/state-machine WPs) + **`gemini-4-hydrogen-high`** Verifiers (`workspace="inherit"`, slashes escaped defects 4× for `+$0.069`).
   - **Mode B (`run_workflow(parallel=...)`)**: For parallel batch recon, lint sweeps, and structured JSON map-reduce (`flash` / `gemini-4-hydrogen-medium`; `low` for grep/JSON; `high` for AST/type checks). (Calls to stateful or single-threaded MCP servers stay serialized across workers or via `pipeline()`.)
   - **Mode A (`invoke_subagent`)**: For single-shot Phase 0 `research` scouts (`flash_lite`/`flash`) and isolated atomic `self` tasks (`flash`/`inherit`). Bounded same-WP follow-up `send_message` is allowed while `< 45` active steps.
4. **Pillar 4 — Zero Watchdog Spam**: Rely on Antigravity's native reactive wakeup; do NOT emit per-turn `schedule(TimerCondition="any")` calls (at most 1 active opt-in watchdog for long-running external/MCP tasks).

---

## 1. v2.0.0 Three-Family Model Matrix & Post-Dec 1, 2026 Economics

All three Gemini 4 families share a `1,048,576`-token (1M) context window where **thinking tokens are billed at the full output rate**, and **implicit prefix caching** (`> 4,096` tokens) delivers a **95% input read discount** (`0.05×` input) vs cold prefill (`1.25×` input) — a 25× unit-cost gap.

| Family | Thinking / Level | Exact Model ID / Alias | Post-Promo In / Out / Cache Read (`/1M`) | Primary Cognitive Role & Target |
| :--- | :--- | :--- | :--- | :--- |
| **Hydrogen** | **Low** | `gemini-4-hydrogen-low` (`flash_lite`) | `$1.50` / `$7.50` / `$0.075` | Instant Recon, grep/JSON transforms (`invoke_subagent`, `run_workflow`). |
| **Hydrogen** | **Medium** | `gemini-4-hydrogen-medium` (`flash`) | `$1.50` / `$7.50` / `$0.075` | Routine Execution, Phase 0 scouts, **Mode C Authors (`workspace="share"`)**, Mode B default. |
| **Hydrogen** | **High** | `gemini-4-hydrogen-high` (`inherit` / `Main`) | `$1.50` / `$7.50` / `$0.075` | **Mode C Verifiers (`workspace="inherit"`)**, selective complex Authors, Mode B AST/types. |
| **Neon** | **Low** | `gemini-4-neon-low` | `$3.00` / `$15.00` / `$0.15` | Quota-throttle Main Session (`40–15%`) or pure mechanical dispatch (`$1.95` weighted). |
| **Neon** | **Medium** | `gemini-4-neon-medium` | `$3.00` / `$15.00` / `$0.15` | **Default Main Session** (`$2.07`, `1.07×` Ultra, `$0` fork to Neon) & Single-WP `@planner`. |
| **Neon** | **High** | `gemini-4-neon-high` | `$3.00` / `$15.00` / `$0.15` | **Multi-WP `@planner`** (`~110 tok/s`, `65.2%` TB-4.1), **Tier-1 `@councillor`**, deep Phase 0.5 Main override. |
| **Carbon** | **Low / Medium / High** | `gemini-4-carbon-low/medium/high` | `$4.00` / `$20.00` / `$0.20` | **Tier-2 `@councillor`** (`high`, `88.2%` SWE-bench), **Gated `@auditor`** (`> 3` WPs/security), formal Main (`medium`). |

### Hard Bans & Manual Picker Overrides
- **Explicitly Banned (Hard-Blocked by `orchestrator_guard.py`)**:
  - **NEVER** use `Orchestrator (Neon)` (`gemini-pro-orchestrator-neon`) or `Orchestrator (Carbon)` (`gemini-pro-orchestrator`) — causes `$0.447–$0.585` KV-cache collapse, `plan_mode` hook collision blocking `scratch/brainstorm_notes.md`, silent `gemini-flash-worker-agy` scout bloat, and post-`exit_plan_mode` `fork="coordinator"` races.
  - **NEVER** use any **`xhigh`** mode (`gemini-4-hydrogen-xhigh`, `gemini-4-neon-xhigh`, or invalid `gemini-4-carbon-xhigh` which returns `HTTP 400`).
  - **NEVER** spawn `@auditor` for routine `<= 3` WP tasks.
- **Rare Main Session Manual Picker Overrides (Leaving `gemini-4-neon-medium`)**:
  1. **Promote to `gemini-4-neon-high`** (`$2.22`, `1.15×` Ultra): Multi-service greenfield design requiring 5+ turns of deep Phase 0.5 `Brainstorming`.
  2. **Promote to `gemini-4-carbon-medium`** (`$2.39`, `1.24×` Ultra): Formal verification, lock-free concurrency, or cryptographic threat-modeling dialogue.
  3. **Demote to `gemini-4-neon-low`** (`$1.95`, `1.01×` Ultra) or **`gemini-4-hydrogen-high`** (`$2.04`, `1.06×` Ultra): Pure mechanical dispatch with pre-written specs or rolling quota `< 40%`.

---

## 2. Phase 0: Parallel Reconnaissance (Pre-Plan Lookup)

### A. Ephemeral Subagent Scouts (`invoke_subagent`)
1. Launch read-only scouts via `invoke_subagent(TypeName="research", Model="flash" | "flash_lite")`. (`TypeName="self"` is hard-blocked for recon).
2. **Budget**: Max **25 steps** or **420s active time** (excluding `429 RESOURCE_EXHAUSTED` gaps).
3. **Parallel Fan-Out**: Launch 2–4 scouts in one turn for `>= 2` independent targets.
4. **Native Wakeup & Single-Shot Kill**: Rely on reactive wakeup (no per-turn `schedule` spam). Kill completed scouts via `manage_subagents(Action="kill" / "kill_all")`; `send_message` to `research` is hard-blocked.

### B. Dynamic Parallel Recon Workflow (`run_workflow`) Template
```python
# Save in <artifactDirectoryPath>/scratch/recon_workflow.py and run via run_workflow
phase("Phase 0 Reconnaissance")
targets = [{"module": "backend", "path": "src/backend"}, {"module": "tests", "path": "tests"}]
recon_schema = {
    "type": "object",
    "properties": {
        "module": {"type": "string"},
        "key_symbols": {"type": "array", "items": {"type": "string"}},
        "constraints": {"type": "array", "items": {"type": "string"}},
        "relevant_files": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["module", "key_symbols", "constraints", "relevant_files"],
}

async def scout_target(item):
    prompt = f"Role: Reconnaissance Scout\nInspect {item['path']} (READ-ONLY). Return key symbols, constraints, and files."
    a = agent(prompt=prompt, schema=recon_schema, role=f"Scout {item['module']}", model="flash")
    return await a(prompt, recon_schema)

results = await parallel(targets, scout_target)
print(results)
```

> [!WARNING]
> **Serialized Single-Threaded MCP Protection**: Never dispatch simultaneous parallel calls to stateful or single-threaded MCP servers. Serialize via a single worker or `pipeline()` in `run_workflow`.

---

## 3. Phase 0.5: Pre-Grilling Mode Selector, Grill-Me & Brainstorming (`ask_question`)

1. **Phase 0 Recap & Mode Selector**: Present a concise **2–4 bullet recap** of Phase 0 recon findings and invoke `ask_question` offering 3 modes (dynamically placing `(Recommended)` first based on task ambiguity and scope):
   - `Standard grill-me` — targeted alignment interview (one question at a time, `(Recommended)` first) resolving concrete ambiguities, trade-offs, and defaults.
   - `No grilling needed` — bypass grilling for clear/menial tasks and proceed directly to Phase 1 (`@planner`).
   - `Brainstorming` — deep collaborative ideation into minute detail until full mutual understanding is reached.
2. **Explicit Prompt Overrides**: If the user's prompt already explicitly selects a mode (e.g., *"skip grilling"*, *"no grilling"*, *"let's brainstorm"*), honor it directly without asking a redundant mode-selector question.
3. **Structured Brainstorming Checklist**:
   - Ask **one focused topic per question** via `ask_question` covering: **Goals**, **UX / User Flows**, **Architecture & Data Contracts**, **Edge Cases**, **Failure Modes**, **Non-Goals**, and **Acceptance Criteria**.
   - Periodically recap emerging consensus.
   - Include an explicit alignment-lock exit option (*"We're fully aligned — lock spec and proceed to Planning"*) once key dimensions are covered.
   - Upon locking alignment, **MANDATORILY** write `<artifactDirectoryPath>/scratch/brainstorm_notes.md` before spawning `@planner`:

```markdown
# Brainstorm & Alignment Notes
## 1. Core Goal & Success Criteria
- ...
## 2. User Flows / UX & Interfaces
- ...
## 3. Architecture & Data Contracts
- ...
## 4. Edge Cases & Failure Modes
- ...
## 5. Explicit Non-Goals & Constraints
- ...
## 6. Acceptance & Verification Criteria
- ...
```

---

## 4. Phase 1: Two-Stage Neon `@planner` Bridge (`implementation_plan.md` → Lazy `kanban/`)

> [!NOTE]
> Full Stage 1A/1B templates, `kanban/board.md` schemas, and `kanban/WP-XX_<slug>.md` card schemas live exclusively in **`skills/orchestrator-planner/SKILL.md`** so non-planner sessions never pay context tax for planner schemas.

Execute `swarm(action="title")` and `swarm(action="add")` in **separate turns**:

```python
# Turn 1: Name swarm
swarm(action="title", title="Implementation Planning")
```

```python
# Turn 2 (Stage 1A — Lean Human Control Plan):
# Use gemini-4-neon-high for multi-WP (Mode B/C); gemini-4-neon-medium for single-WP (Mode A) or minor revisions.
swarm(
    action="add",
    name="planner",
    model="gemini-4-neon-high",
    fork="coordinator",
    workspace="inherit",
    brief="""You are the dedicated Swarm Architect (@planner).
Read skills/orchestrator-planner/SKILL.md for full Stage 1A/1B schemas.
Stage 1A: Draft ONLY <parentArtifactDirectoryPath>/implementation_plan.md using Phase 0 recon & Phase 0.5 choices (read <parentArtifactDirectoryPath>/scratch/brainstorm_notes.md if present).
Post '@coordinator STATUS: PLAN_READY - [2-sentence summary]' and sleep via swarm_wait.""",
)
```

```python
# Turn 3: Wait passively (zero token cost)
swarm_wait(since=0)
# For pre-approval revisions: post_message(text="@planner ...") + swarm_wait(since=last_seq)
```

```python
# Post-Approval (Stage 1B — Lazy Kanban Materialization): Wake sleeping @planner (warm KV cache)
post_message(
    text="""@planner Plan approved. Materialize <parentArtifactDirectoryPath>/kanban/board.md and <parentArtifactDirectoryPath>/kanban/WP-XX_<slug>.md cards per skills/orchestrator-planner/SKILL.md.
Post '@coordinator STATUS: KANBAN_READY - <wave & card summary>' and return to swarm_wait."""
)
swarm_wait(since=last_seq)
```

---

## 5. Phase 2: Execution Fleet Modes & Copy-Pasteable Templates

### Mode C (Primary for Multi-File/Multi-Step Coding): Asymmetric Swarm (`Med` Author + `High` Verifier)
```python
# Turn 1: Title
swarm(action="title", title="Core Refactoring")
```
```python
# Turn 2: Add Author (gemini-4-hydrogen-medium, workspace="share") and Verifier (gemini-4-hydrogen-high, workspace="inherit")
swarm(
    action="add",
    name="author",
    model="gemini-4-hydrogen-medium",  # selective gemini-4-hydrogen-high for complex algorithmic/state-machine WPs
    workspace="share",
    brief="""You own WP-01. Read ONLY <parentArtifactDirectoryPath>/kanban/WP-01_core.md (do NOT read skill files).
Implement changes and run targeted tests. When ready, post '@verifier Ready for verification.' and sleep with swarm_wait.""",
)
swarm(
    action="add",
    name="verifier",
    model="gemini-4-hydrogen-high",
    workspace="inherit",
    brief="""Wait for @author. Inspect changes against <parentArtifactDirectoryPath>/kanban/WP-01_core.md (do NOT read skill files) and run full verification.
Post '@coordinator STATUS: COMPLETED' (or '@author Defects: ...') and sleep with swarm_wait.""",
)
```
```python
# Turn 3: Passive wait (no schedule spam)
swarm_wait(since=0)
```

### Mode B (Parallel Batch Recon / Sweeps): Dynamic Python Workflow (`run_workflow`)
```python
phase("Batch Migration")
files = ["src/a.py", "src/b.py"]
schema = {"type": "object", "properties": {"file": {"type": "string"}, "status": {"type": "string"}}, "required": ["file", "status"]}

async def update_file(path):
    a = agent(prompt=f"Follow <parentArtifactDirectoryPath>/kanban/WP-02_batch.md to update {path} to v2.0.0 API and call finish.", schema=schema, role=f"Editor {path}", model="flash")
    return await a(f"Update {path}", schema)

results = await parallel(files, update_file)
```

### Mode A (Isolated Atomic Tasks): Ephemeral Subagent (`invoke_subagent`)
```python
invoke_subagent(
    TypeName="self",
    Role="Implementation Engineer",
    Model="flash",  # or "inherit"
    Prompt="""Task: Execute WP-03 by reading <artifactDirectoryPath>/kanban/WP-03_atomic.md.
Constraints: Follow workspace security and zero-trust rules; do not scrape transcript.jsonl.
Reporting: End by calling send_message with STATUS: COMPLETED, CLARIFICATION_NEEDED, or ESCALATE_REQUIRED.""",
)
# Bounded same-WP follow-up send_message is allowed while < 45 active steps; kill when done.
```

---

## 6. Guard Rules, Circuit Breakers, Two-Tier Escalation & Quota Playbook (`v2.0.0`)

### A. Budgets, Wakeup Reset, & Hand-Off
* **Ephemeral `invoke_subagent`**: `25` steps / `420s` active (RO `research`), `45` steps / `600s` active (RW `self`), excluding `429 RESOURCE_EXHAUSTED` retry gaps.
* **Persistent Swarm Workers**: Exempt from global wall-clock timeout; per-wakeup budgets of `35` steps (RO `@councillor` / RO `@auditor`) or `60` steps (RW Swarm workers). `step_count` and turn timer reset on every wakeup.
* **6 `CIRCUIT_BREAKER_EXEMPT_TOOLS`**: `send_message`, `read_board`, `swarm_wait`, `post_message`, `manage_subagents`, `schedule`.
* **Mandatory CB Hand-Off**: When CB triggers, workers MUST immediately call `send_message` or `post_message` (`STATUS: COMPLETED` or `STATUS: ESCALATE_REQUIRED`) — never exit via plain text.

### B. Two-Tier Escalation Gate (`Neon` → `Carbon`)
`orchestrator_guard.py` blocks `>= 2` consecutive `invoke_subagent` retries after `STATUS: ESCALATE_REQUIRED`, `CIRCUIT BREAKER`, `NO_VALID_SEND`, or retry keywords (`fix`, `retry`, `remaining`, `pass 2`, `pass_2`) until `@councillor` posts a strategy or `ask_question` is answered:

```python
# Tier-1: Spawn Read-Only Neon High @councillor (workspace="inherit")
swarm(
    action="add",
    name="councillor",
    model="gemini-4-neon-high",
    fork="coordinator",
    workspace="inherit",
    brief="""You are @councillor (strictly READ-ONLY).
Diagnose root cause of failure in Step X and post '@coordinator STRATEGY: [concrete fix steps]'.""",
)
swarm_wait(since=last_seq)

# Tier-2: Upgrade in-place to Carbon High ONLY if Tier-1 Neon fails to resolve deadlock (saves $0.532 vs cold spawn)
swarm(action="model", name="councillor", model="gemini-4-carbon-high")
post_message(text="@councillor Deeper deadlock on edge case Y. Re-evaluate root cause.")
swarm_wait(since=last_seq)
```

### C. `/usage` Four-Stage Quota Throttle Playbook
Inspect `/usage` or `/quota` proactively and apply in-place downgrades via `swarm(action="model")` before touching the `$40.00/mo` Google Cloud overflow account:
1. **Stage 1 (`100–40%` — Nominal)**: Standalone `gemini-4-neon-medium` Main + `gemini-4-neon-high` multi-WP `@planner` + `Hydrogen Medium` Authors + `Hydrogen High` Verifiers + Tier-1 `Neon High` → Tier-2 `Carbon High` `@councillor` + gated `Carbon High` `@auditor` (`> 3` WPs/security).
2. **Stage 2 (`40–15%` — Throttle)**: Switch Main to `gemini-4-neon-low` (`$1.95`, preserves `$0` fork), pin all `@planner` runs to `gemini-4-neon-medium`, disable speculative `Hydrogen High` Author promotions, and enforce `retry_streak >= 2` before Carbon.
3. **Stage 3 (`< 15%` or `[quota]` Warning — Survival)**: Call `swarm(action="model")` in-place to step Main to `gemini-4-hydrogen-medium` and Mode C fleet to `Med+Med`, pause non-blocking `@auditor`, and prefer Mode B `run_workflow`.
4. **Stage 4 (`0%` — `$40` Cloud Backup)**: For hard deadlines only, switch login to `$40.00/mo` Cloud credits and run the Stage 2/3 Lean Profile (`~19.4–20.8` sessions per `$40`), then switch back when Ultra resets.

### D. Operational Quirks & Anti-Bloat Rules
* **Operational Quirks**:
  - **Thinking Skip**: UI dropdown resets can trigger zero-reasoning tool calls; verify model/effort after UI reloads.
  - **1M Context Pruning**: Long trajectories still degrade on raw log bloat; stage large outputs in `<artifactDirectoryPath>/scratch/`.
  - **Implicit Caching Only**: `cachedContents` API returns `HTTP 400`; rely on implicit prefix caching (`> 4,096` tokens) via same-family `fork="coordinator"`.
* **Isolation & Payload Boundaries**:
  - **Main Session Write & Kanban Boundary**: Writes strictly inside `<artifactDirectoryPath>/scratch/`; direct `implementation_plan.md` and `kanban/**` writes are blocked.
  - **`@planner`-Only Write Lock**: Only `@planner` may write `<parentArtifactDirectoryPath>/implementation_plan.md` and `<parentArtifactDirectoryPath>/kanban/**`.
  - **Cross-Session Scratch & Kanban Boundary**: Workers may access `<parentArtifactDirectoryPath>/scratch/` (RW) and `<parentArtifactDirectoryPath>/kanban/**` (RO); stale `/brain/<other_id>/` directories are blocked.
  - **`[MCP_ONLY]` & Read-Only Blocks**: `[MCP_ONLY]` locks out `run_command` and `WRITE_FILE_TOOLS`; `research`, `@councillor`, and RO-flagged `@auditor` are blocked from mutating tools and `STATE_MODIFYING_MCP_TOOLS`.
  - **Payload Caps**: `MAX_SUBAGENT_PROMPT_CHARS = 3500`, `MAX_RETURN_MESSAGE_CHARS = 2500`.
