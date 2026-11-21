# Token-Efficient Task Orchestrator — Windows Edition (v2.0.0)

This directory is a complete, self-contained **Windows** drop-in edition of the **Token-Efficient Task Orchestrator (v2.0.0 — Three-Family Model Matrix)** plugin for Google Antigravity.

> [!CAUTION]
> **Experimental Software — Use Strictly at Your Own Risk**
>
> Review `hooks/orchestrator_guard.py`, `rules/AGENTS.md`, `skills/token-efficient-orchestrator/SKILL.md`, and `skills/orchestrator-planner/SKILL.md` before installing, or have your AI coding agent inspect and adapt them to your environment. See the [root README](../README.md) for the full architecture and guard matrix.

---

## 🪟 Windows Specifics

* **Hook command (`hooks.json`)**: Uses `python -B hooks/orchestrator_guard.py` (standard Windows `python.exe` launcher, suppressing `__pycache__` writes).
* **Cross-platform path handling**: `hooks/orchestrator_guard.py` normalizes Windows drive paths (`C:\...`, `c:/...`), UNC paths, and MSYS/Git-Bash paths consistently.

---

## 📂 Contents

```text
windows/
├── hooks.json
├── plugin.json
├── README.md
├── hooks/
│   └── orchestrator_guard.py
├── rules/
│   └── AGENTS.md
├── skills/
│   ├── orchestrator-planner/
│   │   └── SKILL.md
│   └── token-efficient-orchestrator/
│       └── SKILL.md
└── tests/
    ├── __init__.py
    └── test_orchestrator_guard.py
```

---

## 📦 Installation (Windows)

Copy the contents of `windows/` into your Google Antigravity plugins directory at `%USERPROFILE%\.gemini\config\plugins\orchestrator\`:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.gemini\config\plugins\orchestrator" | Out-Null
Copy-Item -Recurse -Force ".\windows\*" "$env:USERPROFILE\.gemini\config\plugins\orchestrator\"
```

Then enable the `orchestrator` plugin in Antigravity's **Plugins Manager**.

Optional environment variable:
* `ORCHESTRATOR_STATE_MODIFYING_MCP_TOOLS`: Comma-separated list of additional MCP tool names or suffixes to block in Read-Only sessions (`research`, `@councillor`, RO `@auditor`).

---

## 🧪 Running Tests (Windows)

From the `windows/` directory (or installed plugin directory):

```powershell
python -B -m unittest discover -s tests -v
```

Or from the repository root:

```powershell
python -B -m unittest discover -s windows/tests -v
```
