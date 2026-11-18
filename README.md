# Token-Efficient Task Orchestrator (v1.0 — Three-Family Model Matrix)

> [!CAUTION]
> **Experimental Software — Use Strictly at Your Own Risk**
>
> This orchestrator is an **experimental project** provided **"AS IS"** with **zero warranty** and **zero liability**. By using it, you accept full responsibility for all outcomes—the author assumes **no liability** (*not my problem*) for any agent lock-ups, infinite or retry loops, excessive token/quota burn, inefficiencies, blocked tool calls, or unexpected agent behavior.
>
> **Recommended Installation Approach:** Instead of a direct, blind drop-in installation, **inspect the source code and rules first** (`hooks/orchestrator_guard.py`, `rules/AGENTS.md`, `skills/token-efficient-orchestrator/SKILL.md`), or **have your own AI coding agent review, adapt, and install it** to fit your specific environment, tools, and workflow needs.

A high-precision, token-efficient cognitive orchestration system for **Google Antigravity**. Built around the **Three-Family Model Matrix** (`Hydrogen` + `Argon` + `Carbon` + `Orchestrator (Argon)/(Carbon)`): **Hydrogen** (4 thinking levels: Low, Medium, High, XHigh) handling 80%+ of Recon and Execution, **Argon** (3 thinking levels: Low, Medium, High) powering the Dedicated Swarm Planner (`@planner`) and Tier-1 Councillor (`@councillor`), and **Carbon** (3 thinking levels: Low, Medium, High) reserved strictly for Tier-2 `@councillor` deadlock escalation and critical security & compliance audits (`@auditor`).

---

## 🚀 Key Architectural Pillars

### 1. Main Session Commander (Pure Dispatcher)
* **Supported Models**: `Hydrogen High` (`gemini-4-hydrogen-high`), `Orchestrator (Argon)` (`gemini-pro-orchestrator-argon`) for faster/lower-token dispatch, or `Orchestrator (Carbon)` (`gemini-pro-orchestrator`) for ultra-complex multi-system orchestration.
* **Platform-Level Guard**: Enforced via `orchestrator-pure-dispatcher-guard` (`hooks/orchestrator_guard.py`). The Main Session is physically blocked from executing workspace file edits, shell commands (`run_command`), web searches, MCP tools, **writing outside `<artifactDirectoryPath>/scratch/`**, and **directly writing or editing `implementation_plan.md`**.

### 2. Dedicated Swarm Planner & Two-Tier Councillor (`Argon` → `Carbon`)
* **Dedicated Swarm Planner (`@planner`)**: Spawned sequentially (`swarm(action="title")` then `swarm(action="add", name="planner", model="gemini-4-argon-medium", fork="coordinator", workspace="inherit", brief="...")` in separate turns).
  * **Warm Coordinator Fork**: Inherits complete Phase 0 recon and Phase 0.5 Grill-Me history via `fork="coordinator"`.
  * **Artifact-Only Author**: Exclusively authors and updates `<parentArtifactDirectoryPath>/implementation_plan.md` (`gemini-4-argon-low` for minor edits, `gemini-4-argon-medium` default, `gemini-4-argon-high` for complex architecture).
  * **Zero Token Cost in Standby**: Sleeps in `waiting` state at zero token cost until nudged via `post_message`.
* **Two-Tier Councillor (`@councillor`) & Escalation Gate**:
  * **Tier-1 (`Argon`)**: Spawned via `swarm(action="add", name="councillor", model="gemini-4-argon-medium", fork="coordinator", workspace="inherit", brief="...")`. Strictly **Read-Only** (`orchestrator_guard.py` hard-blocks file writes, mutating MCP tools, and mutating shell commands).
  * **Tier-2 (`Carbon`)**: Upgraded in-place via `swarm(action="model", name="councillor", model="gemini-4-carbon-medium")` (or `high`) ONLY if Tier-1 Argon cannot resolve the deadlock.
  * **Guard-Enforced Escalation Gate**: `orchestrator_guard.py` blocks `>= 2` consecutive `invoke_subagent` retries after `STATUS: ESCALATE_REQUIRED`, `CIRCUIT BREAKER`, `NO_VALID_SEND`, or retry keywords (`fix`, `retry`, `remaining`, `pass 2`) until `@councillor` posts a strategy or `ask_question` is consulted.

### 3. 80%+ Hydrogen Execution Fleet & Token-Efficiency Architecture
* **Mode C — Full Native Swarm (`workspace="share"`)**: **Primary** for multi-file/multi-step coding. Preserves KV-cache across edits and tests, eliminates cold-start waste, and enables peer-to-peer Author + Verifier collaboration (`gemini-4-hydrogen-medium/high/xhigh`).
* **Mode B — Dynamic Python Workflows (`run_workflow(parallel=...)`)**: For parallel batch reconnaissance, lint/audit sweeps, and schema-constrained JSON map-reduce pipelines (`flash`). (Calls to stateful or single-threaded MCP servers stay serialized across workers or via `pipeline()`.)
* **Mode A — Ephemeral Subagents (`invoke_subagent`)**: Reserved for single-shot Phase 0 `research` scouts (`flash_lite`/`flash`) and isolated atomic tasks (`self`). Bounded same-WP follow-up `send_message` is permitted for active Phase 2 `self` workers (`< 45` active steps); `research` scouts are strictly single-shot and must be killed upon completion.
* **Zero Polling & Watchdog Spam**: Relies on Antigravity's native reactive wakeup instead of per-turn `schedule(TimerCondition="any")` spam (at most 1 active opt-in watchdog for long-running external/MCP tasks).

### 4. Phase 0.5 Mandatory Post-Recon "Grill-Me" Alignment & Shared Scratch
* Immediately after Phase 0 recon, the Main Session interviews the user via `ask_question` (one question at a time, recommended option first) before `@planner` drafts `implementation_plan.md`.
* Large payloads are staged in `<artifactDirectoryPath>/scratch/` (`MAX_SUBAGENT_PROMPT_CHARS = 3500`, `MAX_RETURN_MESSAGE_CHARS = 2500`).

---

## 📊 The Three-Family Fleet Matrix (`v1.0`)

| Family | Thinking / Variant | Exact Model ID / Subagent Alias | Primary Cognitive Role | Typical Workloads & Target |
| :--- | :--- | :--- | :--- | :--- |
| **Orchestrator** | **Argon / Carbon** | `gemini-pro-orchestrator-argon` / `gemini-pro-orchestrator` | **Main Session Pure Dispatcher** | Fast low-token dispatch (`Argon`), or ultra-complex multi-system orchestration (`Carbon`). |
| **Hydrogen** | **Low** | `gemini-4-hydrogen-low` (`invoke_subagent: flash_lite`) | Instant Recon & Mechanical | Pre-plan file discovery, log grepping, CSV/JSON transforms, CLI lookups. |
| **Hydrogen** | **Medium** | `gemini-4-hydrogen-medium` (`invoke_subagent: flash`, `run_workflow: flash`) | Routine Execution & Scripting | Deep file/case inspection, routine scripts, unit tests, standard Mode C Swarm edits. |
| **Hydrogen** | **High** | `gemini-4-hydrogen-high` (`Main Session`, `invoke_subagent: inherit`) | Main Commander & Workhorse | Pure Dispatcher (`Main Session`), multi-file refactoring, Swarm Author/Verifier (`workspace="share"`). |
| **Hydrogen** | **XHigh** | `gemini-4-hydrogen-xhigh` (`swarm`) | Deepest Hydrogen Execution | Concurrency/race debugging, escalated Hydrogen execution retries (`workspace="share"`). |
| **Argon** | **Low / Medium / High** | `gemini-4-argon-low/medium/high` (`swarm`) | **`@planner` & Tier-1 `@councillor`** | Fast interactive `1M`-context planning (`@planner`) & first-line root-cause diagnosis (`@councillor`, `workspace="inherit"`). |
| **Carbon** | **Low / Medium / High** | `gemini-4-carbon-low/medium/high` (`swarm`) | **Tier-2 `@councillor` & Critical Audits** | Surgical `1M`-context deadlock escalation (`swarm(action="model", ...)`), critical security & compliance audits (`@auditor`). |

---

## 📂 Folder Structure

```text
orchestrator/
├── .gitignore                          # Excludes Python bytecode, caches, and env files
├── LICENSE                             # MIT License
├── hooks.json                          # PreToolUse guard hook registration
├── hooks/
│   └── orchestrator_guard.py           # Pure-dispatcher, swarm, & subagent boundary guard (v1.0)
├── plugin.json                         # Plugin manifest (v1.0.0)
├── README.md                           # Architecture and reference guide
├── rules/
│   └── AGENTS.md                       # Mandatory global orchestrator rule (v1.0)
├── skills/
│   └── token-efficient-orchestrator/
│       └── SKILL.md                    # Full Three-Family routing matrix & operational templates
└── tests/
    ├── __init__.py
    └── test_orchestrator_guard.py      # Automated unit & regression test suite
```

---

## 🛡️ PreToolUse Guard Rules Summary (`orchestrator_guard.py` v1.0)

| Session Type | Tool / Condition | Decision | Behavior / Reason |
| :--- | :--- | :--- | :--- |
| **Main Session** | `run_command`, `search_web`, `mcp_*`, `call_mcp_tool` | **`deny`** | Pure Dispatcher boundary enforcement. |
| **Main Session** | `read_file` / `write_file` / `edit_file` | **`allow` (scoped)** | Reads: `<artifactDir>/` & skill/plugin configs. Writes: strictly `<artifactDir>/scratch/`. Direct `implementation_plan.md` writes denied. |
| **Main Session** | `invoke_subagent` (Prompt > 3,500 chars or Phase 0 with `self`) | **`deny`** | Anti-bloat cap (`MAX_SUBAGENT_PROMPT_CHARS = 3500`) & strict `TypeName="research"` for recon. |
| **Main Session** | `invoke_subagent` (`retry_streak >= 2` after escalation/CB/retry cues) | **`deny`** | Two-Tier Escalation Gate: consult `@councillor` (Argon → Carbon) or `ask_question`. |
| **Main Session** | `send_message` to `research` or `>= 45` active steps | **`deny`** | `research` scouts are single-shot; `self` workers allow bounded follow-up `< 45` active steps (excluding `read_board`, `swarm_wait`). |
| **Main Session** | `swarm`, `post_message`, `read_board`, `swarm_wait`, `run_workflow`, `ask_question`, `schedule`, `manage_task`, `manage_subagents`, `define_subagent` | **`allow`** | Native Antigravity 2.0 orchestration permitted. |
| **Subagent / Swarm** | `ask_question` | **`deny`** | Enforces bubble-up to Main Session with `STATUS: CLARIFICATION_NEEDED`. |
| **Subagent / Swarm** | `send_message` (> 2,500 chars) | **`deny`** | Anti-bloat cap (`MAX_RETURN_MESSAGE_CHARS = 2500`). Stage large payloads in `scratch/`. |
| **Subagent / Swarm** | `[MCP_ONLY]` worker calling `run_command` or `WRITE_FILE_TOOLS` | **`deny`** | Enforces direct `call_mcp_tool` execution without shell/file detours. |
| **Subagent / Swarm** | Read/exec targeting stale `/brain/<other_id>/scratch/` | **`deny`** | Stale-scratch boundary: only own or resolved parent `<parentArtifactDir>` allowed. |
| **Ephemeral `invoke_subagent`** | `>= 25` steps / `420s` active (RO) or `>= 45` steps / `600s` active (RW) | **`deny` (CB)** | Excludes `429 RESOURCE_EXHAUSTED` gaps. Must immediately call `send_message` (`STATUS: COMPLETED` / `ESCALATE_REQUIRED`). |
| **Persistent Swarm** | `>= 35` steps (RO `@councillor`/RO `@auditor`) or `>= 60` steps (RW) per wakeup | **`deny` (CB)** | Exempt from global wall-clock timeout; counters reset on every wakeup. Must call `post_message` + `swarm_wait`. |
| **CB Exempt Tools** | `send_message`, `read_board`, `swarm_wait`, `post_message`, `manage_subagents`, `schedule` | **`allow`** | All 6 `CIRCUIT_BREAKER_EXEMPT_TOOLS` remain permitted during CB hand-off. |
| **Read-Only (`research`, `@councillor`, RO `@auditor`)** | `WRITE_FILE_TOOLS`, `STATE_MODIFYING_MCP_TOOLS` (incl. mutating mail, draft, event, task, and document tools), mutating `run_command` | **`deny`** | Hard Read-Only isolation. |

---

## 📦 Installation

> [!IMPORTANT]
> **Do not blindly drop this plugin into a production setup.** Review `hooks/orchestrator_guard.py`, `rules/AGENTS.md`, and `skills/token-efficient-orchestrator/SKILL.md` first, or ask your own AI coding agent to inspect the repository, tailor the guard rules and model IDs to your environment, and handle the installation for you.

If you want to install manually after reviewing and adapting the configuration:
1. Copy or clone this repository into your Google Antigravity plugins directory (e.g., `~/.gemini/config/plugins/orchestrator/`).
2. Review and customize any workspace-specific rules, model IDs, and circuit-breaker thresholds to match your workflow.
3. Enable the `orchestrator` plugin in Antigravity's Plugins Manager.

Optional environment configuration:
* `ORCHESTRATOR_STATE_MODIFYING_MCP_TOOLS`: Comma-separated list of additional MCP tool names or suffixes to block in Read-Only sessions (`research`, `@councillor`, RO `@auditor`).

---

## 🧪 Running Tests

Run the unit and regression test suite without writing `.pyc` bytecode caches:

```bash
python -B -m pytest tests -v
```

---

## 📄 License

This project is licensed under the **MIT License** — see [LICENSE](LICENSE) for details.
