# Token-Efficient Task Orchestrator — Linux Edition (v1.2.0)

This directory is a complete, self-contained **Linux** drop-in edition of the **Token-Efficient Task Orchestrator (v1.2 — Three-Family Model Matrix)** plugin for Google Antigravity.

> [!CAUTION]
> **Experimental Software — Use Strictly at Your Own Risk**
>
> Review `hooks/orchestrator_guard.py`, `rules/AGENTS.md`, and `skills/token-efficient-orchestrator/SKILL.md` before installing, or have your AI coding agent inspect and adapt them to your environment. See the [root README](../README.md) for the full architecture and guard matrix.

---

## 🐧 Linux Specifics

* **Hook command (`hooks.json`)**: Uses `python3 -B hooks/orchestrator_guard.py` (standard POSIX `python3`, suppressing `__pycache__` writes).
* **Executable permissions**: `.py` files under `hooks/` and `tests/` ship with `+x` permissions (`chmod +x`).
* **POSIX hardening**: `hooks/orchestrator_guard.py` includes non-blocking `stdin` parsing, FIFO/named-pipe protection, Linux POSIX Read-Only command blocking, and strict hook-CWD isolation.

---

## 📂 Contents

```text
linux/
├── hooks.json
├── plugin.json
├── README.md
├── hooks/
│   └── orchestrator_guard.py
├── rules/
│   └── AGENTS.md
├── skills/
│   └── token-efficient-orchestrator/
│       └── SKILL.md
└── tests/
    ├── __init__.py
    └── test_orchestrator_guard.py
```

---

## 📦 Installation (Linux)

Copy the contents of `linux/` into your Google Antigravity plugins directory at `~/.gemini/config/plugins/orchestrator/`:

```bash
mkdir -p ~/.gemini/config/plugins/orchestrator
cp -a ./linux/. ~/.gemini/config/plugins/orchestrator/
chmod +x ~/.gemini/config/plugins/orchestrator/hooks/orchestrator_guard.py
```

Then enable the `orchestrator` plugin in Antigravity's **Plugins Manager**.

Optional environment variable:
* `ORCHESTRATOR_STATE_MODIFYING_MCP_TOOLS`: Comma-separated list of additional MCP tool names or suffixes to block in Read-Only sessions (`research`, `@councillor`, RO `@auditor`).

---

## 🧪 Running Tests (Linux)

From the `linux/` directory (or installed plugin directory):

```bash
python3 -B -m unittest discover -s tests -v
```

Or from the repository root:

```bash
python3 -B -m unittest discover -s linux/tests -v
```
