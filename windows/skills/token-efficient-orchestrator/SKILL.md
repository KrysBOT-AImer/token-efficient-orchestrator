---
name: token-efficient-orchestrator
description: >-
  Orchestrates multi-step tasks with the v6.0 Three-Family Model Matrix: Hydrogen (Low/Medium/High/XHigh)
  for 80%+ Recon & Execution (Mode B run_workflow + persistent Mode C Swarm), Argon (Low/Medium/High)
  for Dedicated Swarm Planner (@planner) & Tier-1 Councillor (@councillor), Carbon (Low/Medium/High) for
  Tier-2 @councillor deadlock escalation & critical security & compliance audits (@auditor), plus
  Orchestrator (Argon)/(Carbon) Main Session Dispatcher.
---

# Token-Efficient Task Orchestrator (v6.0 — Three-Family Cognitive Architecture)

This skill governs Antigravity's `v6.0` cognitive orchestration architecture:
1. **Pillar 1 — Main Session Pure Dispatcher**: Runs on `Hydrogen High` (`gemini-4-hydrogen-high`), `Orchestrator (Argon)` (`gemini-pro-orchestrator-argon`) for faster/lower-token dispatch, or `Orchestrator (Carbon)` (`gemini-pro-orchestrator`) for ultra-complex multi-system orchestration. Direct workspace edits, `run_command`, web search, MCP calls, writes outside `<artifactDirectoryPath>/scratch/`, and direct `implementation_plan.md` authoring are physically blocked by `orchestrator_guard.py`.
2. **Pillar 2 — Dedicated Swarm `@planner` (`Argon`) & Two-Tier `@councillor` (`Argon` → `Carbon`)**:
   - **`@planner`**: Spawned sequentially (`swarm(action="title")` then `swarm(action="add", name="planner", model="gemini-4-argon-medium", fork="coordinator", workspace="inherit", ...)` in separate turns). Exclusive author of `<parentArtifactDirectoryPath>/implementation_plan.md`.
   - **Tier-1 `@councillor` (`Argon`)**: Spawned with `model="gemini-4-argon-medium"`, `fork="coordinator"`, `workspace="inherit"`. Strictly **Read-Only** (enforced by `orchestrator_guard.py`).
   - **Tier-2 `@councillor` (`Carbon`) & `@auditor`**: Upgrade `@councillor` in-place via `swarm(action="model", name="councillor", model="gemini-4-carbon-medium")` (or `high`) ONLY when Argon hits a deadlock; spawn `@auditor` (`gemini-4-carbon-medium/high`) for critical security & compliance audits (RO-enforced when RO-flagged).
3. **Pillar 3 — 80%+ Hydrogen Execution Fleet (Mode C Primary)**:
   - **Mode C (`swarm`, `workspace="share"`)**: **Primary** for multi-file/multi-step coding (preserves KV-cache across edits & tests).
   - **Mode B (`run_workflow(parallel=...)`)**: For parallel batch recon, lint sweeps, and structured JSON map-reduce (`flash`). (Calls to stateful or single-threaded MCP servers stay serialized across workers or via `pipeline()`.)
   - **Mode A (`invoke_subagent`)**: For single-shot Phase 0 `research` scouts (`flash_lite`/`flash`) and isolated atomic `self` tasks (`flash`/`inherit`). Bounded same-WP follow-up `send_message` is allowed while `< 45` active steps.
4. **Pillar 4 — Zero Watchdog Spam**: Rely on Antigravity's native reactive wakeup; do NOT emit per-turn `schedule(TimerCondition="any")` calls (at most 1 active opt-in watchdog for long-running external/MCP tasks).

---

## 1. The Three-Family Model Matrix (`v6.0`)

| Family | Thinking / Variant | Exact Model ID / Subagent Alias | Primary Cognitive Role | Typical Workloads & Execution Target |
| :--- | :--- | :--- | :--- | :--- |
| **Orchestrator** | **Argon** | `gemini-pro-orchestrator-argon` | **Fast Main Dispatcher** | Lower-token, low-latency Pure Dispatcher (`Main Session`). |
| **Orchestrator** | **Carbon** | `gemini-pro-orchestrator` | **Deep Main Dispatcher** | Ultra-complex multi-system orchestration (`Main Session`). |
| **Hydrogen** | **Low** | `gemini-4-hydrogen-low` (`invoke_subagent: flash_lite`) | Instant Recon & Mechanical | File discovery, log grepping, CSV/JSON transforms, CLI lookups. Target: `invoke_subagent(Model="flash_lite")`, `run_workflow`. |
| **Hydrogen** | **Medium** | `gemini-4-hydrogen-medium` (`invoke_subagent: flash`, `run_workflow: flash`) | Routine Execution & Scripting | Deep file/case inspection, routine scripts, unit tests, standard Mode C Swarm edits (`workspace="share"`). |
| **Hydrogen** | **High** | `gemini-4-hydrogen-high` (`Main Session`, `invoke_subagent: inherit`) | Main Commander & Workhorse | Pure Dispatcher (`Main Session`), multi-file refactoring, Swarm Author/Verifier (`workspace="share"`). |
| **Hydrogen** | **XHigh** | `gemini-4-hydrogen-xhigh` (`swarm`) | Deepest Hydrogen Execution | Concurrency/race debugging, escalated Hydrogen retries (`swarm(..., workspace="share")`). |
| **Argon** | **Low / Medium / High** | `gemini-4-argon-low/medium/high` (`swarm`) | **`@planner` & Tier-1 `@councillor`** | `1M` context, fast interactive loops, lower token spend. `fork="coordinator"`, `workspace="inherit"`. |
| **Carbon** | **Low / Medium / High** | `gemini-4-carbon-low/medium/high` (`swarm`) | **Tier-2 `@councillor` & Critical Audits** | `1M` context frontier reasoning. `swarm(action="model")` deadlock upgrade or `@auditor` (security & compliance). |

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

## 3. Phase 0.5: Mandatory Post-Recon "Grill-Me" Alignment (`ask_question`)

1. Interview the user via `ask_question` **one question at a time** with `(Recommended)` first.
2. **Deterministic Checkpoint**: Even when 100% clear, ask at least 1 confirmation question offering `"(Recommended) Proceed directly to Implementation Plan artifact with these defaults"`.

---

## 4. Phase 1: Argon Swarm Bridge (`@planner`) & Artifact-Only Plan

Execute `swarm(action="title")` and `swarm(action="add")` in **separate turns**:

```python
# Turn 1: Name swarm
swarm(action="title", title="Implementation Planning")
```

```python
# Turn 2: Add @planner (Argon Medium default; Low for minor edits; High for complex architecture)
swarm(
    action="add",
    name="planner",
    model="gemini-4-argon-medium",
    fork="coordinator",
    workspace="inherit",
    brief="""You are the dedicated Swarm Architect (@planner).
Draft <parentArtifactDirectoryPath>/implementation_plan.md using Phase 0 recon & Phase 0.5 choices.
Include: 1. Recon & Grill-Me Summary, 2. Subagent Execution & Model Routing Table, 3. Proposed Changes, 4. Verification Plan.
Use ArtifactMetadata: {RequestFeedback: true, UserFacing: true, Summary: '...'}.
Post '@coordinator STATUS: PLAN_READY - [2-sentence summary]' and sleep via swarm_wait.""",
)
```

```python
# Turn 3: Wait passively (zero token cost)
swarm_wait(since=0)
# For revisions: post_message(text="@planner ...") + swarm_wait(since=last_seq)
```

---

## 5. Phase 2: Execution Fleet Modes & Copy-Pasteable Templates

### Mode C (Primary for Multi-File/Multi-Step Coding): Full Native Swarm (`workspace="share"`)
```python
# Turn 1: Title
swarm(action="title", title="Core Refactoring")
```
```python
# Turn 2: Add Author (workspace="share") and Verifier (workspace="inherit")
swarm(
    action="add",
    name="author",
    model="gemini-4-hydrogen-medium",  # or gemini-4-hydrogen-high / xhigh
    workspace="share",
    brief="""You own Step 1 of <parentArtifactDirectoryPath>/implementation_plan.md.
Implement changes and run targeted tests. When ready, post '@verifier Ready for verification.' and sleep with swarm_wait.""",
)
swarm(
    action="add",
    name="verifier",
    model="gemini-4-hydrogen-high",
    workspace="inherit",
    brief="""Wait for @author. Inspect changes and run full verification.
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
    a = agent(prompt=f"Update {path} to v6.0 API and call finish.", schema=schema, role=f"Editor {path}", model="flash")
    return await a(f"Update {path}", schema)

results = await parallel(files, update_file)
```

### Mode A (Isolated Atomic Tasks): Ephemeral Subagent (`invoke_subagent`)
```python
invoke_subagent(
    TypeName="self",
    Role="Implementation Engineer",
    Model="flash",  # or "inherit"
    Prompt="""Task: Execute Step X in <artifactDirectoryPath>/implementation_plan.md.
Constraints: Follow workspace security and zero-trust rules; do not scrape transcript.jsonl.
Reporting: End by calling send_message with STATUS: COMPLETED, CLARIFICATION_NEEDED, or ESCALATE_REQUIRED.""",
)
# Bounded same-WP follow-up send_message is allowed while < 45 active steps; kill when done.
```

---

## 6. Guard Rules, Circuit Breakers, & Two-Tier Escalation (`orchestrator_guard.py` v6.0)

### A. Budgets, Wakeup Reset, & Hand-Off
* **Ephemeral `invoke_subagent`**: `25` steps / `420s` active (RO `research`), `45` steps / `600s` active (RW `self`), excluding `429 RESOURCE_EXHAUSTED` retry gaps.
* **Persistent Swarm Workers**: Exempt from global wall-clock timeout; per-wakeup budgets of `35` steps (RO `@councillor` / RO `@auditor`) or `60` steps (RW Swarm workers). `step_count` and turn timer reset on every wakeup.
* **6 `CIRCUIT_BREAKER_EXEMPT_TOOLS`**: `send_message`, `read_board`, `swarm_wait`, `post_message`, `manage_subagents`, `schedule`.
* **Mandatory CB Hand-Off**: When CB triggers, workers MUST immediately call `send_message` or `post_message` (`STATUS: COMPLETED` or `STATUS: ESCALATE_REQUIRED`) — never exit via plain text.

### B. Two-Tier Escalation Gate (`Argon` → `Carbon`)
`orchestrator_guard.py` blocks `>= 2` consecutive `invoke_subagent` retries after `STATUS: ESCALATE_REQUIRED`, `CIRCUIT BREAKER`, `NO_VALID_SEND`, or retry keywords (`fix`, `retry`, `remaining`, `pass 2`, `pass_2`) until `@councillor` posts a strategy or `ask_question` is answered:

```python
# Tier-1: Spawn Read-Only Argon @councillor (workspace="inherit")
swarm(
    action="add",
    name="councillor",
    model="gemini-4-argon-medium",
    fork="coordinator",
    workspace="inherit",
    brief="""You are @councillor (strictly READ-ONLY).
Diagnose root cause of failure in Step X and post '@coordinator STRATEGY: [concrete fix steps]'.""",
)
swarm_wait(since=last_seq)

# Tier-2: Upgrade in-place to Carbon ONLY if Tier-1 Argon fails to resolve deadlock
swarm(action="model", name="councillor", model="gemini-4-carbon-medium")  # or gemini-4-carbon-high
post_message(text="@councillor Deeper deadlock on edge case Y. Re-evaluate root cause.")
swarm_wait(since=last_seq)
```

### C. Special Isolation & Anti-Bloat Rules
* **Main Session Write Boundary**: Strictly `<artifactDirectoryPath>/scratch/`.
* **Cross-Session Scratch**: Workers may access `<parentArtifactDirectoryPath>/scratch/`; stale `/brain/<other_id>/` directories are blocked.
* **`[MCP_ONLY]` Tag**: Adding `[MCP_ONLY]` to a worker's Role/Prompt blocks `run_command` and `WRITE_FILE_TOOLS`, forcing direct `call_mcp_tool` calls.
* **Read-Only Hard Blocks**: `research`, `@councillor`, and RO-flagged `@auditor` are blocked from `WRITE_FILE_TOOLS`, mutating `run_command`, and `STATE_MODIFYING_MCP_TOOLS` (including `render_document`, `save_draft`, and mutating mail/draft/folder/event/contact/task/category/rule/oof tools).
* **Payload Caps**: `MAX_SUBAGENT_PROMPT_CHARS = 3500`, `MAX_RETURN_MESSAGE_CHARS = 2500`.
