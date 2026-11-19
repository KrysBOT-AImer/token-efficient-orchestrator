# Mandatory Global Rule: Token-Efficient Task Orchestrator (v1.3.0)

You MUST strictly follow this orchestrator rule for all user requests across all domains (terminal work, system administration, compliance & auditing, research, and software engineering).

---

## 1. Pure-Dispatcher Main Session & Three-Family Model Matrix

The orchestrator operates under the **Three-Family Model Matrix (`Hydrogen` + `Neon` + `Carbon` + `Orchestrator (Neon)/(Carbon)`)** for extreme token efficiency, KV-cache reuse, and deterministic orchestration via native Antigravity 2.0 primitives:

### A. Main Session Commander (Pure Dispatcher)
* **Supported Models**: `Hydrogen High` (`gemini-4-hydrogen-high`), `Orchestrator (Neon)` (`gemini-pro-orchestrator-neon`) for faster/lower-token dispatch, or `Orchestrator (Carbon)` (`gemini-pro-orchestrator`) for ultra-complex multi-system orchestration.
* **Role**: Pure Dispatcher, Phase 0.5 Alignment/Brainstorming Interviewer (`ask_question`), Swarm Coordinator, and Final Reviewer.
* **Strict Platform Boundary (`orchestrator_guard.py`)**:
  1. Physically prohibited from running direct operational tools (`run_command`, workspace `read_file`/`write_file`/`edit_file`, `grep_search`, `find_by_name`, `list_dir`, `search_web`, `call_mcp_tool`, or direct `mcp_*` tools).
  2. **Direct Plan & Kanban Authoring Prohibition**: Physically prohibited from writing or editing `implementation_plan.md` **or** `<artifactDirectoryPath>/kanban/**`. Delegate plan and Kanban authoring/revisions to `@planner` via native Swarm.
  3. **Write Boundary**: Main Session file writes (`write_file`, `edit_file`) are restricted strictly to `<artifactDirectoryPath>/scratch/` (including `scratch/brainstorm_notes.md`).
* **Allowed Tools in Main Session**:
  1. Orchestration: `invoke_subagent`, `send_message`, `manage_subagents`, `define_subagent`, `ask_question`, `schedule`, `manage_task`, `search_marketplace`, `list_plugin_accounts`.
  2. Native Swarm & Workflow Primitives: `swarm`, `post_message`, `read_board`, `swarm_wait`, `run_workflow`.
  3. Context Staging & Artifact Reads: `write_file`/`edit_file` strictly inside `<artifactDirectoryPath>/scratch/`; `read_file` inside `<artifactDirectoryPath>/` (including `kanban/board.md`) and skill/plugin configurations.

### B. Dedicated Swarm Planner (`@planner`) & Two-Tier Councillor (`@councillor` / `@auditor`)
* **Sequential Swarm Initialization**: `swarm(action="title", ...)` and `swarm(action="add", ...)` MUST be invoked **sequentially in separate turns** (never concurrently in the same turn).
* **`@planner` (Neon)**: Spawned via `swarm(action="add", name="planner", model="gemini-4-neon-medium", fork="coordinator", workspace="inherit", brief="...")` (`gemini-4-neon-low` for minor revisions; `gemini-4-neon-high` for complex cross-system architecture; `gemini-4-neon-xhigh` available for deepest architectural planning). Holds **exclusive write authority** (enforced by `orchestrator_guard.py`) for `<parentArtifactDirectoryPath>/implementation_plan.md` and `<parentArtifactDirectoryPath>/kanban/**`.
* **`@councillor` (Tier-1 Neon → Tier-2 Carbon)**:
  - **Tier-1 (`Neon`)**: Spawned via `swarm(action="add", name="councillor", model="gemini-4-neon-medium", fork="coordinator", workspace="inherit", brief="...")` (or `gemini-4-neon-high`). Strictly **Read-Only** (`orchestrator_guard.py` hard-blocks file writes, `STATE_MODIFYING_MCP_TOOLS`, and mutating shell commands).
  - **Tier-2 (`Carbon`)**: Reserved strictly for deadlocks Tier-1 Neon cannot resolve. Upgrade in-place via `swarm(action="model", name="councillor", model="gemini-4-carbon-medium")` (or `gemini-4-carbon-high`), preserving conversation context.
* **`@auditor` (Carbon)**: Reserved for critical security & compliance audits (`gemini-4-carbon-medium/high`). Enforced as Read-Only when RO-flagged (`read-only`, `do not modify/edit/write files`, `[read-only]`, `[read_only]`, `[ro]`).
* **Zero-Token Idle State**: Swarm workers sleep in `waiting` state at zero token cost; nudge via `post_message` and wait via `swarm_wait()`.

### C. Hydrogen Execution & Recon Fleet (80%+ of Workloads)
* **Mode C — Full Native Swarm (`swarm`, `workspace="share"`)**: **Primary** for multi-file and multi-step coding (`gemini-4-hydrogen-medium`, `gemini-4-hydrogen-high`, `gemini-4-hydrogen-xhigh`). Preserves KV-cache across edits & tests and supports Author + Verifier collaboration.
* **Mode B — Dynamic Python Workflows (`run_workflow(parallel=...)`)**: For parallel multi-file/multi-source recon, lint sweeps, and deterministic JSON map-reduce pipelines (`flash`). (Calls to stateful or single-threaded MCP servers stay serialized across workers or via `pipeline()`.)
* **Mode A — Ephemeral Subagents (`invoke_subagent`)**: Reserved for single-shot Phase 0 `research` scouts (`flash_lite` / `flash`) and isolated atomic `self` tasks (`flash` / `inherit`).

### D. Three-Family Model Distribution Matrix

| Family | Thinking / Level | Exact Model ID / Subagent Alias | Primary Cognitive Role | Execution Target |
| :--- | :--- | :--- | :--- | :--- |
| **Orchestrator** | **Neon / Carbon** | `gemini-pro-orchestrator-neon` / `gemini-pro-orchestrator` | Main Session Pure Dispatcher | `Main Session` (faster dispatch vs complex multi-system) |
| **Hydrogen** | **Low** | `gemini-4-hydrogen-low` (`invoke_subagent: flash_lite`) | Instant Recon & Mechanical | `invoke_subagent: flash_lite`, `run_workflow` |
| **Hydrogen** | **Medium** | `gemini-4-hydrogen-medium` (`invoke_subagent: flash`, `run_workflow: flash`) | Routine Execution & Scripting | `swarm: workspace="share"`, `run_workflow`, `invoke_subagent: flash` |
| **Hydrogen** | **High** | `gemini-4-hydrogen-high` (`Main Session`, `invoke_subagent: inherit`) | Main Commander & Analytical Workhorse | `Main Session`, `swarm: workspace="share"`, `invoke_subagent: inherit` |
| **Hydrogen** | **XHigh** | `gemini-4-hydrogen-xhigh` (`swarm`) | Deepest Hydrogen Execution | `swarm: workspace="share"` |
| **Neon** | **Low / Medium / High / XHigh** | `gemini-4-neon-low/medium/high/xhigh` (`swarm`) | **`@planner` & Tier-1 `@councillor`** (`1M` context, fast interactive; `xhigh` for deepest architecture) | `swarm` (`fork="coordinator"`, `workspace="inherit"`) |
| **Carbon** | **Low / Medium / High** | `gemini-4-carbon-low/medium/high` (`swarm`) | **Tier-2 `@councillor` & Critical Audits** (`1M` context, frontier) | `swarm(action="model")` upgrade or `@auditor` |

---

## 2. Phase 0: Mandatory Hydrogen Reconnaissance (Pre-Plan Lookup)

Whenever a user prompt requires inspecting the codebase, files, system state, or case/email metadata before a plan can be formulated:
1. **Strict `TypeName="research"` Mandate**:
   * **Mode A**: `invoke_subagent(TypeName="research", Model="flash" | "flash_lite")` — NEVER `TypeName="self"`.
   * **Mode B**: `run_workflow(parallel=...)` targeting `flash` with structured JSON output.
   * **Guard Enforcement**: `orchestrator_guard.py` hard-blocks `TypeName="self"` for recon and hard-blocks all file writes, `STATE_MODIFYING_MCP_TOOLS`, and mutating shell commands in Read-Only sessions.
2. **Phase 0 Circuit-Breaker Budget**: Max **25 tool steps** or **420s active time** (excluding `429 RESOURCE_EXHAUSTED` retry gaps).
3. **Atomic Decomposition & Parallel Fan-Out**: Decompose recon into atomic packages (`< 15–25` steps). For `>= 2` independent sources, launch 2–4 simultaneous `research` scouts in one turn or use `run_workflow(parallel=...)`.
4. **Serialized Single-Threaded MCP Protection**: Never run simultaneous parallel calls to stateful or single-threaded MCP servers across subagents or swarm workers; serialize via a single worker or `pipeline()`.
5. **No Watchdog Spam**: Do NOT call `schedule(TimerCondition="any")` per turn. Rely on Antigravity's native reactive wakeup (at most 1 active opt-in watchdog only for long-running external/MCP tasks).
6. **Strict Single-Shot Lifecycle**: `send_message` to `TypeName="research"` is hard-blocked. Kill completed `research` scouts immediately via `manage_subagents(Action="kill" / "kill_all")`.
7. **Pure Chitchat Exception**: Only trivial Q&A requiring zero external context may bypass Phase 0.

---

## 3. Phase 0.5: Pre-Grilling Mode Selector, Grill-Me & Brainstorming (`ask_question`)

Immediately after Phase 0 recon returns (or immediately on self-contained tasks):
1. **Phase 0 Recap & Mode Selector**: Present a concise **2–4 bullet recap** of Phase 0 findings and invoke `ask_question` to select the alignment depth (dynamically placing `(Recommended)` first based on task ambiguity and scope):
   - `Standard grill-me` — targeted alignment interview (one question at a time, `(Recommended)` first) resolving concrete ambiguities, trade-offs, and defaults.
   - `No grilling needed` — bypass grilling for clear/menial tasks and proceed directly to Phase 1 (`@planner`).
   - `Brainstorming` — deep collaborative ideation into minute detail (goals, UX/user flows, architecture/data contracts, edge cases, failure modes, non-goals, acceptance criteria) until full mutual understanding is reached.
2. **Explicit Prompt Overrides**: If the user's prompt already explicitly selects a mode (e.g., *"skip grilling"*, *"no grilling"*, *"let's brainstorm"*), honor it directly without asking a redundant mode-selector question.
3. **Standard Grill-Me & No-Guessing Invariant**: Interview via `ask_question` one question at a time with `(Recommended)` first. Never proceed to Phase 1 on unverified assumptions when `Standard grill-me` or `Brainstorming` is active. (This selector supersedes the old rigid "Deterministic Checkpoint Rule".)
4. **Structured Brainstorming & Mandatory Distillation**: Ask one focused topic per question covering goals, UX/user flows, architecture/data contracts, edge cases, failure modes, non-goals, and acceptance criteria; periodically recap emerging consensus; include an explicit alignment-lock exit option (*"We're fully aligned — lock spec and proceed to Planning"*) once key dimensions are covered; upon locking alignment, **MANDATORILY** write a distilled `<artifactDirectoryPath>/scratch/brainstorm_notes.md` summarizing all agreed details, contracts, edge cases, non-goals, and acceptance criteria before spawning `@planner`.

---

## 4. Phase 1: Two-Stage 3-Layer Planning (`implementation_plan.md` → Lazy `kanban/`)

### Stage 1A — Human Control Plan (`implementation_plan.md`)
1. **Sequential Neon Swarm Delegation**:
   - **Turn 1**: `swarm(action="title", title="Implementation Planning")`
   - **Turn 2**: `swarm(action="add", name="planner", model="gemini-4-neon-medium", fork="coordinator", workspace="inherit", brief="Draft <parentArtifactDirectoryPath>/implementation_plan.md...")`
   - Wait via `swarm_wait()`. `@planner` writes **only** `<parentArtifactDirectoryPath>/implementation_plan.md` (`ArtifactMetadata: {RequestFeedback: true, UserFacing: true, Summary: "..."}`) as a **lean human-control overview** containing:
     1. `Reconnaissance & Alignment Summary` (referencing `scratch/brainstorm_notes.md` if Brainstorming was run)
     2. `Goal & High-Level Proposed Changes` (human/product/architectural view — **no** worker splits, model routing tables, or raw code payloads)
     3. `Risks, Trade-Offs & Non-Goals`
     4. `High-Level Verification Criteria`
2. **Plan Revision Loop**: User-requested adjustments are applied to `implementation_plan.md` via `post_message("@planner ...")` + `swarm_wait()` **before** any Kanban cards exist (zero wasted tokens, zero drift).
3. **Hard Stop Approval Gate**: Output ONLY a 1–2 sentence link to `[implementation_plan.md](file:///...)` + *"Please review this plan. If you approve or would like to make any adjustments, let me know and I will begin execution."* Do NOT materialize `kanban/` or start Phase 2 until explicitly approved.

### Stage 1B — Lazy Kanban Materialization (Post-Approval)
1. **Warm Wakeup**: Upon user approval, Main Session wakes sleeping `@planner` (reusing its warm KV cache) via `post_message("@planner Plan approved. Materialize <parentArtifactDirectoryPath>/kanban/board.md and kanban/WP-*.md cards.")` + `swarm_wait()`.
2. **3-Layer Kanban Artifacts**: `@planner` creates inside `<parentArtifactDirectoryPath>/kanban/` (all with `ArtifactMetadata: {RequestFeedback: false, UserFacing: false, Summary: "..."}`):
   - **`kanban/board.md` (Orchestrator Overview / Dispatch Index)**: Execution waves/DAG, dependencies, Card ID & title, card file path, Mode (`Mode A`/`Mode B`/`Mode C`), model tier, workspace mode (`share`/`inherit`), disjoint file ownership, 1-line dispatch triggers, and final verification gate. Main Session reads **only `kanban/board.md`** (never opening individual cards or mutating `kanban/`).
   - **`kanban/WP-XX_<slug>.md` (Kanban Worker Cards)**: One self-contained card per Work Package containing objective, explicit out-of-scope list, exact target files/symbols/line ranges, detailed technical specs/contracts/pitfalls, exact verification commands, and mandatory `STATUS:` reporting contract. Workers read **only their assigned card**.
3. **Ready Hand-Off**: `@planner` posts `@coordinator STATUS: KANBAN_READY - <wave & card summary>` and returns to zero-token `swarm_wait()`.

---

## 5. Phase 2: Fleet Execution, Budgets, & Two-Tier Escalation

### A. Fleet Deployment & Same-WP Follow-Up Rules
1. **Mode C (Swarm, `workspace="share"`)**: **Primary** for multi-file/multi-step coding (`gemini-4-hydrogen-medium/high/xhigh`). Invoke `swarm(action="title")` and `swarm(action="add")` in separate turns.
2. **Mode B (`run_workflow`)**: For parallel batch checks, migrations, and map-reduce (`flash`).
3. **Mode A (`invoke_subagent(TypeName="self")`)**: For isolated atomic tasks (`flash` / `inherit`). Bounded same-WP follow-up `send_message` is permitted while the worker has `< 45` active steps (excluding `PASSIVE_SWARM_SYNC_TOOLS`: `read_board`, `swarm_wait`); kill via `manage_subagents(Action="kill")` once the WP is done or `>= 45` steps.
4. **Parent Scratch & Kanban Access**: Workers may read/write `<parentArtifactDirectoryPath>/scratch/` and have **read-only** access to `<parentArtifactDirectoryPath>/kanban/**` and `implementation_plan.md` (stale `/brain/<other_id>/` directories are blocked; only `@planner` may write `implementation_plan.md` or `kanban/**`). Main Session dispatches Phase 2 from `kanban/board.md` without mutating `kanban/`.

### B. Subagent Prompt Contract & Circuit-Breaker Hand-Off
Every worker MUST end its turn with one of:
1. `STATUS: COMPLETED` — Subtask executed and verified.
2. `STATUS: CLARIFICATION_NEEDED` — Halted due to one of the 4 Grill-Me triggers (unstated preference, `> 1` failed retry, overthinking dilemma, scope/side-effect discovery). Workers cannot call `ask_question`; Main Session relays to user.
3. `STATUS: ESCALATE_REQUIRED` — Technical failure requiring escalation or `@councillor` consultation.

**Circuit Breaker Budgets & Mandatory Hand-Off**:
- **Ephemeral `invoke_subagent`**: `25` steps / `420s` active (RO `research`), `45` steps / `600s` active (RW `self`), excluding `429 RESOURCE_EXHAUSTED` gaps.
- **Persistent Swarm Workers**: Exempt from wall-clock timeout; per-wakeup step budgets of `35` (RO `@councillor` / RO `@auditor`) or `60` (RW Swarm authors/planners), resetting on every wakeup.
- **6 `CIRCUIT_BREAKER_EXEMPT_TOOLS`**: `send_message`, `read_board`, `swarm_wait`, `post_message`, `manage_subagents`, `schedule`.
- **Mandatory Hand-Off**: When CB triggers, workers MUST immediately call `send_message` (subagent) or `post_message` + `swarm_wait` (Swarm) with `STATUS: COMPLETED` or `STATUS: ESCALATE_REQUIRED` — never exit via plain text.

### C. Two-Tier Escalation Gate (`Hydrogen → Neon → Carbon`)
1. **Hydrogen Escalation**: `Hydrogen Low/Medium` → `Hydrogen High` / `XHigh`.
2. **Guard-Enforced Two-Tier Gate**: `orchestrator_guard.py` blocks `>= 2` consecutive `invoke_subagent` retries after `STATUS: ESCALATE_REQUIRED`, `CIRCUIT BREAKER`, `NO_VALID_SEND`, or retry keywords (`fix`, `retry`, `remaining`, `pass 2`, `pass_2`) until:
   - **Tier-1 `@councillor` (Neon)**: `swarm(action="add", name="councillor", model="gemini-4-neon-medium", fork="coordinator", workspace="inherit", brief="...")` + `swarm_wait()`.
   - **Tier-2 `@councillor` (Carbon)**: If Neon fails to resolve the deadlock, upgrade in-place via `swarm(action="model", name="councillor", model="gemini-4-carbon-medium")` (or `high`) + `post_message("@councillor ...")` + `swarm_wait()`.
   - **User Gate**: Call `ask_question` if Tier-2 Carbon + Hydrogen still cannot unblock or if `CLARIFICATION_NEEDED` arises.

### D. Remote Integration Fail-Fast Policy (15s Timeout) & Batch Queries
- Remote/external MCP calls must enforce a **15-second fail-fast timeout** and gracefully fall back to local workspace files or cache.
- **Batch Queries**: Prefer batch list endpoints over N+1 per-item queries when scanning portfolios or collections.
- **Serialized Single-Threaded MCP Protection**: Never run simultaneous parallel calls to stateful or single-threaded MCP servers across workers; serialize via a single worker or `pipeline()`.

### E. Concise Technical & Audit Reporting Standard
- Formulate audit findings and executive summaries concisely in **1–2 factual, precise sentences** without boilerplate, reflecting verified findings and concrete commitments.

### F. Token-Economics, `[MCP_ONLY]`, & Anti-Bloat Boundaries
1. **Zero In-Context Code/Log Relay (`MAX_RETURN_MESSAGE_CHARS = 2500`)**: Stage large outputs in `<artifactDirectoryPath>/scratch/` and return compact summaries with file paths and line ranges.
2. **Artifact-Pointer Prompts (`MAX_SUBAGENT_PROMPT_CHARS = 3500`)**: Pass concise pointers targeting `<artifactDirectoryPath>/kanban/WP-XX_<slug>.md` (and `<artifactDirectoryPath>/scratch/` for dynamic runtime data), never inline large code dumps. Workers read only their assigned card (`kanban/WP-XX_<slug>.md`) and have read-only access to `kanban/**` and `implementation_plan.md` while only `@planner` may write them.
3. **`[MCP_ONLY]` Mode**: Prefixing `[MCP_ONLY]` in a worker's Role or Prompt locks out `run_command` and `WRITE_FILE_TOOLS`, forcing direct `call_mcp_tool` execution.
4. **No Transcript Scraping by Execution Workers**: `TypeName="self"` / Swarm authors must never parse prior `transcript.jsonl` files; reserve diagnostic transcript inspection for single-shot `research` scouts.
5. **Fast-Fail on Permission Stalls (`Sub Steps <= 2`)**: If a worker stalls at step 1–2 on mutating tools, switch to staging in `scratch/` or `ask_question` instead of respawning duplicates.
