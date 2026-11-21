#!/usr/bin/env python3
"""
Token-Efficient Task Orchestrator v2.0.0 — PreToolUse Enforcement Guard

Enforces:
1. Pure-Dispatcher Main Session (Gemini 4 Neon Medium default):
   - Prohibits direct execution of terminal commands (run_command), web searches,
     and MCP tool calls in the Main Session.
   - Restricts file reads in the Main Session to conversation artifacts (<artifactDirectoryPath>/,
     including kanban/board.md) and skill/plugin definitions, and restricts Main Session file
     writes strictly to <artifactDirectoryPath>/scratch/ (e.g. scratch/brainstorm_notes.md).
   - Prohibits the Main Session from writing or editing implementation_plan.md or kanban/
     planning artifacts directly; plan and Kanban card authoring must be delegated to the dedicated
     Neon @planner worker via native swarm(action='add', name='planner', model='gemini-4-neon-high', fork='coordinator')
     (or 'gemini-4-neon-medium' for single-WP tasks).
   - Hard-blocks all banned Swarm models unconditionally (Main Session & Swarm workers) on
     swarm(action='add'|'model'): all xhigh / Extra High modes and all gemini-pro-orchestrator* /
     Orchestrator (Neon|Carbon) wrappers.
   - Restricts invoke_subagent: Phase 0 / Read-Only reconnaissance subagents MUST use TypeName='research'.
   - Enforces Two-Tier Escalation Gate: blocks repeated invoke_subagent retry loops
     (retry_streak >= 2 after escalation/CB/retry cues) until @councillor (Tier-1 Neon
     gemini-4-neon-high, or Tier-2 Carbon gemini-4-carbon-high via
     swarm(action='model')) or ask_question is consulted.
   - Restricts send_message: Anti-recycling guards prevent reusing completed read-only
     subagents or overloaded Phase 2 worker subagents (>= 45 active steps).
   - Permits native Antigravity 2.0 swarm & workflow orchestration tools (swarm, post_message,
     read_board, swarm_wait, run_workflow) and user alignment tools (ask_question, schedule).
2. Worker Subagent & Swarm Worker Boundary:
   - Prohibits subagents and swarm workers from calling 'ask_question' directly; they must
     bubble up ambiguities via STATUS: CLARIFICATION_NEEDED.
   - Enforces Step & Active-Time Circuit Breaker with graceful hand-off:
     - Ephemeral invoke_subagent: max 25 steps / 420s active (RO), 45 steps / 600s active (RW),
       excluding 429 RESOURCE_EXHAUSTED retry backoff gaps.
     - Persistent Swarm workers (@planner, @councillor, workspace="share", etc.): exempt from
       global wall-clock timeout; per-wakeup step budgets of 35 (RO, e.g. @councillor) or 60 (RW).
     - Resets step counter and turn timer on every new wakeup prompt.
     - Passive swarm synchronization tools ('read_board', 'swarm_wait') and 'send_message'/
       'post_message' are exempted from tripping the circuit breaker so workers can report safely.
   - Stale-Scratch & Planner-Authority boundary enforcement: allows subagents and swarm workers
     to read/write their own scratch/artifacts and read their resolved parent coordinator's
     scratch, implementation_plan.md, and kanban/ artifacts, while strictly blocking unrelated
     conversation IDs and restricting writes to implementation_plan.md and kanban/ exclusively
     to @planner.
   - Hard Read-Only Enforcement for Read-Only (research / Phase 0 / @councillor / RO @auditor):
     - Blocks file write/edit tools.
     - Blocks state-modifying MCP tools.
     - Blocks state-modifying commands in run_command.
"""

import io
import json
import os
import posixpath
import re
import select
import stat
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

ALLOWED_ORCHESTRATION_TOOLS = {
    "manage_subagents",
    "define_subagent",
    "ask_question",
    "schedule",
    "manage_task",
    "search_marketplace",
    "list_plugin_accounts",
    # Native Swarm & Workflow Orchestration tools (v2.0.0):
    "swarm",
    "post_message",
    "read_board",
    "swarm_wait",
    "run_workflow",
    "enter_plan_mode",
    "exit_plan_mode",
}

SUBAGENT_RO_MAX_STEPS = 25
SUBAGENT_RW_MAX_STEPS = 45
SUBAGENT_RO_MAX_SECONDS = 420.0
SUBAGENT_RW_MAX_SECONDS = 600.0
SWARM_RO_MAX_STEPS = 35
SWARM_RW_MAX_STEPS = 60

PASSIVE_SWARM_SYNC_TOOLS = {
    "read_board",
    "swarm_wait",
}

CIRCUIT_BREAKER_EXEMPT_TOOLS = {
    "send_message",
    "read_board",
    "swarm_wait",
    "post_message",
    "manage_subagents",
    "schedule",
}

WRITE_FILE_TOOLS = {
    "write_file",
    "write_to_file",
    "create_file",
    "edit_file",
    "replace_file_content",
    "multi_replace_file_content",
}
WRITE_TOOLS = WRITE_FILE_TOOLS

READ_FILE_TOOLS = {
    "read_file",
    "view_file",
}

STATE_MODIFYING_MCP_TOOLS = {
    "create_draft",
    "update_draft",
    "delete_draft",
    "batch_create_drafts",
    "send_mail",
    "reply_mail",
    "forward_mail",
    "delete_mail",
    "move_mail",
    "mark_mail",
    "create_folder",
    "create_event",
    "update_event",
    "delete_event",
    "create_contact",
    "update_contact",
    "delete_contact",
    "create_task",
    "update_task",
    "complete_task",
    "delete_task",
    "set_category",
    "toggle_rule",
    "set_oof",
    "render_document",
    "save_draft",
}

STATE_MODIFYING_MCP_REGEX = re.compile(
    r"(?:^|_)(?:create|update|delete|remove|send|reply|forward|move|mark|complete|toggle|set|save|render|write|edit|publish|deploy)(?:_|$)",
    re.IGNORECASE,
)

READ_ONLY_MCP_REGEX = re.compile(
    r"(?:^|_)(?:read|get|list|search|query|fetch|inspect|view|whoami)(?:_|$)",
    re.IGNORECASE,
)


def _get_state_modifying_mcp_tools() -> set[str]:
    """Return configured state-modifying MCP tool names/suffixes."""
    extra_raw = os.environ.get("ORCHESTRATOR_STATE_MODIFYING_MCP_TOOLS", "")
    extra = {t.strip().lower() for t in extra_raw.split(",") if t.strip()}
    return STATE_MODIFYING_MCP_TOOLS | extra


def _is_state_modifying_mcp_tool(name: str) -> bool:
    """Return True if an MCP tool name/suffix matches a mutating tool or verb."""
    normalized = name.strip().lower()
    if not normalized:
        return False
    mutating_tools = _get_state_modifying_mcp_tools()
    if normalized in mutating_tools or any(
        normalized.endswith(f"_{t}") for t in mutating_tools
    ):
        return True
    return bool(
        STATE_MODIFYING_MCP_REGEX.search(normalized)
        and not READ_ONLY_MCP_REGEX.search(normalized)
    )

MUTATING_CMD_PATTERNS = [
    r"\b(Set-Content|Out-File|Add-Content|Remove-Item|Move-Item|Copy-Item|New-Item|Rename-Item|del|rm|rmdir|mkdir|mv|cp|touch|chmod|chown|chgrp|truncate|shred|unlink|ln|install|dd|mkfs|mount|umount|patch)\b",
    r"\bsed\s+(?:-[a-zA-Z]*i|--in-place)\b",
    r"\bperl\s+-[a-zA-Z]*i\b",
    r"\b(?:apt(?:-get)?|dnf|yum)\s+(?:install|remove|purge|upgrade|dist-upgrade|update|autoremove)\b",
    r"\bpacman\s+-(?:S|R|U)[a-zA-Z]*\b",
    r"\bpip3?\s+(?:install|uninstall)\b",
    r"\bnpm\s+(?:install|uninstall|ci|publish)\b",
    r"\bsystemctl\s+(?:start|stop|restart|reload|enable|disable|mask|unmask)\b",
    r"git\s+(commit|push|reset|checkout|clean|merge|rebase|cherry-pick|revert|am|apply)\b",
    r"open\s*\([^)]*['\"][wa\+]['\"]",
    r"\.write_text\s*\(",
    r"\.write_bytes\s*\(",
]

READ_ONLY_CMD_BLOCK_REGEX = re.compile(
    r"(" + "|".join(MUTATING_CMD_PATTERNS) + r")",
    re.IGNORECASE,
)

ROLE_RECON_REGEX = re.compile(
    r"\b(phase\s*0|read[- ]only|recon|reconnaissance|forensic\s+auditor|code\s+state\s+inspector|scout)\b",
    re.IGNORECASE,
)
RECON_REGEX = ROLE_RECON_REGEX

ROLE_EXEC_REGEX = re.compile(
    r"\b(executor|implementer|worker|execution|implementation)\b",
    re.IGNORECASE,
)
ROLE_FORCE_RECON_REGEX = re.compile(
    r"\b(read[- ]only|forensic\s+auditor|code\s+state\s+inspector)\b",
    re.IGNORECASE,
)

PROMPT_RECON_EXPLICIT_PATTERNS = [
    re.compile(r"\bread-only\b", re.IGNORECASE),
    re.compile(r"\bdo\s+not\s+(?:modify|edit|write)\s+(?:any\s+)?files\b", re.IGNORECASE),
    re.compile(r"\byou\s+are\s+(?:a|an)\s+(?:phase\s*0|read[- ]only|recon(?:naissance)?)\b", re.IGNORECASE),
]

PROMPT_RECON_ACTION_PATTERNS = [
    re.compile(r"\b(?:run|perform|execute|conduct)\s+(?:phase\s*0|recon(?:naissance)?)\b", re.IGNORECASE),
]

PROMPT_EXEC_REGEX = re.compile(
    r"\b(execution\s+worker|implementer|executor|apply\s+edits)\b",
    re.IGNORECASE,
)


def detect_recon_invocation(role: str, prompt_raw: str) -> Optional[str]:
    """
    Detects whether an invoke_subagent invocation represents a read-only / scout
    task that was mistakenly invoked with TypeName='self' instead of TypeName='research'.
    Returns the matched trigger phrase if detected, or None if it is a legitimate
    execution / implementation worker.
    """
    role_match = ROLE_RECON_REGEX.search(role)
    has_exec = bool(ROLE_EXEC_REGEX.search(role)) or bool(
        PROMPT_EXEC_REGEX.search(prompt_raw[:500])
    )
    if role_match:
        forced = bool(ROLE_FORCE_RECON_REGEX.search(role))
        if not (has_exec and not forced):
            return role_match.group(0)

    prompt_snippet = prompt_raw[:500]
    for pat in PROMPT_RECON_EXPLICIT_PATTERNS:
        m = pat.search(prompt_snippet)
        if m:
            return m.group(0)

    if not has_exec:
        for pat in PROMPT_RECON_ACTION_PATTERNS:
            m = pat.search(prompt_snippet)
            if m:
                return m.group(0)

    return None

WRAP_UP_REGEX = re.compile(
    r"\b(?:wrap\s+up(?:\s+(?:now|immediately))?|stop\s+(?:now\s+)?and\s+report)\b",
    re.IGNORECASE,
)

FORK_ASSIGNMENT_MARKER = "You have just started. Your assignment (recorded on the board"
FORK_IDENTITY_REGEX = re.compile(
    r"You are @[a-zA-Z0-9_-]+\.\s+Everything before this turn is @"
)
FORK_NOTICE_REGEX = re.compile(
    r"^<fork_notice>[ \t]*\r?$\s*[\s\S]{0,400}?This conversation was branched from a previous conversation\s*\(ID:\s*([a-f0-9-]{36})\)",
    re.IGNORECASE | re.MULTILINE,
)
FORK_ASSIGNMENT_LINE_REGEX = re.compile(
    r"^You have just started\.\s+Your assignment \(recorded on the board",
    re.MULTILINE,
)
FORK_IDENTITY_LINE_REGEX = re.compile(
    r"^You are @([a-zA-Z0-9_-]+)\.\s+Everything before this turn is @",
    re.MULTILINE,
)
SWARM_WORKER_LINE_REGEX = re.compile(
    r"^(?:<swarm_worker>(?!\w)|You are a worker in a native swarm\b)",
    re.MULTILINE,
)
SWARM_WORKER_ROLE_REGEX = re.compile(
    r"<swarm_worker>\s*\r?\n\s*You are ([a-zA-Z0-9_-]+),\s+one agent in a swarm\b",
    re.IGNORECASE | re.MULTILINE,
)
BOARD_ASSIGNMENT_FOR_ROLE_REGEX = re.compile(
    r"You have just started\.\s+Your assignment \(recorded on the board(?:\s+as\s+#\d+)?\s+for\s+@([a-zA-Z0-9_-]+)\)",
    re.IGNORECASE,
)
BOARD_ASSIGNMENT_MENTION_REGEX = re.compile(
    r"You have just started\.\s+Your assignment \(recorded on the board[^)]*\):[^\n]*\r?\n\s*@([a-zA-Z0-9_-]+)\b",
    re.IGNORECASE,
)
BRAIN_ARTIFACT_PATH_REGEX = re.compile(
    r"/brain/([^/]+)/(?:scratch(?:/.*)?|implementation_plan\.md|kanban(?:/.*)?)",
    re.IGNORECASE,
)
BRAIN_ARTIFACT_CMD_REGEX = re.compile(
    r"/brain/([^/\s\"']+)/(?:scratch(?:[/\s\"']|$)|implementation_plan\.md|kanban(?:[/\s\"']|$))",
    re.IGNORECASE,
)
PLANNER_ONLY_ARTIFACT_PATH_REGEX = re.compile(
    r"/brain/([^/]+)/(?:implementation_plan\.md|kanban(?:/.*)?)$",
    re.IGNORECASE,
)
PLANNER_ONLY_ARTIFACT_CMD_REGEX = re.compile(
    r"/brain/([^/\s\"']+)/(?:implementation_plan\.md|kanban(?:[/\s\"']|$))",
    re.IGNORECASE,
)
PLANNER_ONLY_CMD_REDIRECT_REGEX = re.compile(
    r"(?:(?:(?<![0-9])|(?<=1))>{1,2}|\btee\b(?:\s+-[a-zA-Z]+)*)\s*(?:\"[^\"\n]*?|'[^'\n]*?|[^\s;&|'\"]*?)/brain/([^/\s\"']+)/(?:implementation_plan\.md|kanban(?:[/\s\"']|$))",
    re.IGNORECASE,
)


def _is_planner_role(swarm_role: Optional[str]) -> bool:
    """Return True iff the normalized swarm role is 'planner' or 'planner-*'."""
    if not swarm_role or not isinstance(swarm_role, str):
        return False
    role_norm = swarm_role.strip().lstrip("@").lower()
    return role_norm == "planner" or role_norm.startswith("planner-")


BANNED_XHIGH_MODEL_REGEX = re.compile(
    r"(?:^|[\s\-_/()])(?:xhigh|extra[\s\-_]?high)(?:$|[\s\-_/()])",
    re.IGNORECASE,
)
BANNED_ORCHESTRATOR_WRAPPER_REGEX = re.compile(
    r"(?:gemini-pro-orchestrator(?:-neon)?|orchestrator\s*\(\s*(?:neon|carbon)\s*\))",
    re.IGNORECASE,
)


def _check_banned_swarm_model(args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Block banned xhigh modes and gemini-pro-orchestrator* wrappers on swarm add/model."""
    action = str(args.get("action") or "").strip().lower()
    if action not in ("add", "model"):
        return None
    model_raw = str(args.get("model") or args.get("Model") or "").strip()
    if not model_raw:
        return None
    if BANNED_XHIGH_MODEL_REGEX.search(model_raw) or BANNED_ORCHESTRATOR_WRAPPER_REGEX.search(model_raw):
        return {
            "decision": "deny",
            "reason": (
                f"ORCHESTRATOR GUARD BLOCKED (v2.0.0): Model '{model_raw}' is banned for Swarm dispatch. "
                "All xhigh modes and gemini-pro-orchestrator* / Orchestrator (Neon|Carbon) wrappers are prohibited. "
                "Use valid standalone models instead: 'gemini-4-neon-medium' or 'gemini-4-neon-high', "
                "'gemini-4-hydrogen-medium' or 'gemini-4-hydrogen-high', or 'gemini-4-carbon-medium' or 'gemini-4-carbon-high' "
                "(or omit 'model' to inherit the caller's model)."
            ),
        }
    return None
AUDITOR_RO_FLAG_REGEX = re.compile(
    r"(?:\bread[- ]only\b|\bdo\s+not\s+(?:modify|edit|write)\s+(?:any\s+)?files\b|\[read[-_]?only\]|\[ro\])",
    re.IGNORECASE,
)
RETRY_429_REGEX = re.compile(
    r"(?:\b429\b|RESOURCE_EXHAUSTED)",
    re.IGNORECASE,
)
ESCALATION_CUE_REGEX = re.compile(
    r"(?:STATUS:\s*ESCALATE_REQUIRED|CIRCUIT\s+BREAKER|NO_VALID_SEND)",
    re.IGNORECASE,
)
RETRY_KEYWORD_REGEX = re.compile(
    r"\b(?:fix|retry|remaining|pass\s*2|pass_2)\b",
    re.IGNORECASE,
)
INCOMING_MESSAGE_ENVELOPE_REGEX = re.compile(
    r"(?:^\[Message\]\s+(?:timestamp=|sender=)|^\s*<SYSTEM_MESSAGE>\s*\r?\n\s*\[Message\])",
    re.MULTILINE,
)
SUBAGENT_MARKER_1 = "You are running as a subagent, invoked by a caller agent"
SUBAGENT_MARKER_2 = "<subagent_reminder>"

MAX_SUBAGENT_PROMPT_CHARS = 3500
MAX_RETURN_MESSAGE_CHARS = 2500

MAX_SIBLING_BRAIN_SCAN = 25
SIBLING_SCAN_TIME_BUDGET_SEC = 1.5
MAX_FILE_READ_BYTES = 16 * 1024 * 1024
MAX_STDIN_BYTES = 10 * 1024 * 1024
MAX_MESSAGES_SCAN = 128
MAX_PARENT_ID_CACHE_ENTRIES = 64
_PARENT_ID_CACHE: Dict[str, str] = {}
_PARENT_ID_CACHE_LOCK = threading.Lock()

PATH_KEYS = (
    "Path",
    "path",
    "TargetFile",
    "AbsolutePath",
    "Target",
    "FilePath",
    "File",
)

_WIN_DRIVE_REGEX = re.compile(r"^[a-zA-Z]:(?:/|$)")
_CACHE_MISS = object()


def _norm_sep(p: str) -> str:
    return str(p or "").strip().replace("\\", "/")


def _path_basename(p: str) -> str:
    s = _norm_sep(p).rstrip("/")
    return posixpath.basename(s)


def _path_dirname(p: str) -> str:
    s = _norm_sep(p).rstrip("/")
    return posixpath.dirname(s)


def _is_explicit_abs_or_home_path(p: str) -> bool:
    s = _norm_sep(p)
    if not s:
        return False
    if s.startswith("file://"):
        return True
    return s.startswith("/") or s == "~" or s.startswith("~/") or bool(_WIN_DRIVE_REGEX.match(s))


def normalize_path(p: str) -> str:
    if not p or not isinstance(p, str):
        return ""
    s = _norm_sep(p)
    if not s:
        return ""
    if s.startswith("file://"):
        s = s[7:]
        if re.match(r"^/[a-zA-Z]:/", s):
            s = s[1:]
    if s == "~" or s.startswith("~/"):
        s = _norm_sep(os.path.expanduser(s))
    if _WIN_DRIVE_REGEX.match(s):
        return posixpath.normpath(s).lower()
    try:
        if s.startswith("/"):
            return os.path.normcase(posixpath.normpath(s)).replace("\\", "/")
        return os.path.normcase(os.path.abspath(s)).replace("\\", "/")
    except Exception:
        return os.path.normcase(posixpath.normpath(s)).replace("\\", "/")


def is_inside_directory(target_path: str, base_dir: str) -> bool:
    if not target_path or not base_dir:
        return False
    if _is_explicit_abs_or_home_path(base_dir) and not _is_explicit_abs_or_home_path(target_path):
        return False
    norm_target = normalize_path(target_path)
    norm_base = normalize_path(base_dir).rstrip("/")
    if _WIN_DRIVE_REGEX.match(norm_target) or _WIN_DRIVE_REGEX.match(norm_base):
        norm_target = norm_target.lower()
        norm_base = norm_base.lower()
    if norm_target == norm_base:
        return True
    return norm_target.startswith(norm_base + "/")


def extract_target_path(args: Dict[str, Any]) -> Optional[str]:
    for key in PATH_KEYS:
        val = args.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip().strip('"').strip("'")
    return None


def is_allowed_read_path(target_path: str, artifact_dir: Optional[str]) -> bool:
    if not target_path:
        return False

    # 1. Inside current conversation's artifact directory
    if artifact_dir and is_inside_directory(target_path, artifact_dir):
        return True

    if not _is_explicit_abs_or_home_path(target_path):
        return False

    norm_target = normalize_path(target_path)
    norm_lower = norm_target.lower()

    # 2. Inside builtin skills/plugins or config plugins/skills
    allowed_markers = (
        "/.gemini/antigravity/builtin/skills",
        "/.gemini/antigravity/builtin/plugins",
        "/.gemini/antigravity-cli/builtin/",
        "/.gemini/antigravity-ide/builtin/",
        "/.gemini/config/plugins",
        "/.gemini/config/skills",
    )
    if any(marker in norm_lower for marker in allowed_markers):
        return True

    home_dir = normalize_path(os.path.expanduser("~")).rstrip("/")
    for rel_dir in (
        ".gemini/antigravity/builtin/skills",
        ".gemini/antigravity/builtin/plugins",
        ".gemini/antigravity-cli/builtin",
        ".gemini/antigravity-ide/builtin",
        ".gemini/config/plugins",
        ".gemini/config/skills",
    ):
        if is_inside_directory(target_path, f"{home_dir}/{rel_dir}"):
            return True

    return False


def _read_text_with_retry(
    path: str, max_bytes: Optional[int] = None, retries: int = 3
) -> str:
    """
    Reads UTF-8 text from regular file `path` without blocking on FIFOs/devices
    and with brief backoff retries for transient sharing violations.
    """
    if not path:
        return ""
    try:
        st = os.stat(path)
    except OSError:
        return ""
    if not stat.S_ISREG(st.st_mode):
        return ""

    limit = (
        int(max_bytes)
        if (max_bytes is not None and max_bytes >= 0)
        else MAX_FILE_READ_BYTES
    )
    open_flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0)

    for attempt in range(max(1, retries)):
        fd: Optional[int] = None
        try:
            fd = os.open(path, open_flags)
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                return ""
            f = os.fdopen(fd, "r", encoding="utf-8", errors="replace")
            fd = None
            with f:
                return f.read(limit)
        except (PermissionError, BlockingIOError):
            if attempt + 1 < retries:
                time.sleep(0.02 * (attempt + 1))
                continue
            return ""
        except OSError as exc:
            winerr = getattr(exc, "winerror", None)
            if winerr in (32, 33) and attempt + 1 < retries:
                time.sleep(0.02 * (attempt + 1))
                continue
            return ""
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
    return ""


class _BoundedStampCache:
    """Thread-safe bounded cache keyed by normalized path and validated by stamp."""

    def __init__(self, max_entries: int = 16) -> None:
        self.max_entries = max(1, int(max_entries))
        self._lock = threading.Lock()
        self._entries: Dict[str, Tuple[Any, Any]] = {}
        self._order: List[str] = []

    def _get(self, norm_key: str, stamp: Any) -> Any:
        with self._lock:
            cached = self._entries.get(norm_key)
            if cached is not None and cached[0] == stamp:
                return cached[1]
        return _CACHE_MISS

    def _put(self, norm_key: str, stamp: Any, value: Any) -> None:
        with self._lock:
            if norm_key in self._entries:
                self._entries[norm_key] = (stamp, value)
                if norm_key in self._order:
                    self._order.remove(norm_key)
                self._order.append(norm_key)
            else:
                while len(self._order) >= self.max_entries:
                    oldest = self._order.pop(0)
                    self._entries.pop(oldest, None)
                self._entries[norm_key] = (stamp, value)
                self._order.append(norm_key)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._order.clear()


class MessagesCache(_BoundedStampCache):
    """
    Thread-safe bounded cache of parsed .system_generated/messages/*.json dicts
    keyed by normalized directory path and validated by directory mtime and file stamps.
    """

    def get_messages(self, messages_dir: str) -> List[Dict[str, Any]]:
        if not messages_dir or not isinstance(messages_dir, str):
            return []
        try:
            dir_st = os.stat(messages_dir)
        except OSError:
            return []
        if not stat.S_ISDIR(dir_st.st_mode):
            return []

        try:
            filenames = sorted(
                fn for fn in os.listdir(messages_dir)
                if fn.endswith(".json") and fn.lower() != "read.json"
            )[:MAX_MESSAGES_SCAN]
        except OSError:
            return []

        file_entries: List[Tuple[str, str, int, int]] = []
        for fn in filenames:
            msg_file = os.path.join(messages_dir, fn)
            try:
                fst = os.stat(msg_file)
            except OSError:
                continue
            if stat.S_ISREG(fst.st_mode):
                file_entries.append((fn, msg_file, fst.st_mtime_ns, fst.st_size))

        stamp = (
            dir_st.st_mtime_ns,
            tuple((fn, mtime, sz) for fn, _, mtime, sz in file_entries),
        )
        norm_key = normalize_path(messages_dir)
        cached = self._get(norm_key, stamp)
        if cached is not _CACHE_MISS:
            return cached

        messages: List[Dict[str, Any]] = []
        for _, msg_file, _, _ in file_entries:
            try:
                raw_msg = _read_text_with_retry(msg_file, max_bytes=262144)
                if not raw_msg:
                    continue
                msg_data = json.loads(raw_msg)
                if isinstance(msg_data, dict):
                    messages.append(msg_data)
            except Exception:
                continue

        self._put(norm_key, stamp, messages)
        return messages


MESSAGES_CACHE = MessagesCache(max_entries=16)


class TranscriptCache(_BoundedStampCache):
    """
    Thread-safe bounded cache of parsed JSONL transcript records keyed by
    normalized path and validated by (st_mtime_ns, st_size).
    """

    def get_records(self, path: str) -> List[Dict[str, Any]]:
        if not path or not isinstance(path, str):
            return []
        try:
            st = os.stat(path)
        except OSError:
            return []
        if not stat.S_ISREG(st.st_mode):
            return []

        stamp = (st.st_mtime_ns, st.st_size)
        norm_key = normalize_path(path)
        cached = self._get(norm_key, stamp)
        if cached is not _CACHE_MISS:
            return cached

        raw_text = _read_text_with_retry(path)
        if not raw_text:
            return []

        records: List[Dict[str, Any]] = []
        for raw_line in raw_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(rec, dict):
                records.append(rec)

        self._put(norm_key, stamp, records)
        return records

    def clear(self) -> None:
        super().clear()
        MESSAGES_CACHE.clear()


TRANSCRIPT_CACHE = TranscriptCache(max_entries=16)


def _is_system_message_record(record: Dict[str, Any]) -> bool:
    """
    Returns True only for genuine system-injected prompt/assignment records,
    strictly ignoring tool responses (e.g. type == 'TOOL_RESPONSE') and
    user/model records.
    """
    if not isinstance(record, dict):
        return False
    source = str(record.get("source") or "")
    step_type = str(record.get("type") or "")

    if (
        step_type == "TOOL_RESPONSE"
        or step_type.startswith("TOOL_")
        or step_type == "PLANNER_RESPONSE"
        or source == "MODEL"
        or source in ("USER_EXPLICIT", "USER_INPUT")
    ):
        return False
    if record.get("tool_call_id") or record.get("tool_name") or record.get("tool_calls"):
        return False

    if step_type == "SYSTEM_MESSAGE":
        return source in ("", "SYSTEM")
    if source == "SYSTEM" and step_type in ("", "USER_INPUT"):
        return True
    return False


def _is_incoming_message_envelope(content: str) -> bool:
    """
    Returns True if a system record's content is an incoming [Message] relay
    envelope (e.g. a <SYSTEM_MESSAGE> [Message] timestamp=... sender=... content=...
    message delivered from a child subagent or background task).
    """
    if not isinstance(content, str) or not content:
        return False
    return bool(INCOMING_MESSAGE_ENVELOPE_REGEX.search(content))


def _parse_iso_ts(ts_str: Any) -> Optional[datetime]:
    if not ts_str or not isinstance(ts_str, str):
        return None
    try:
        dt = datetime.fromisoformat(ts_str.strip().replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _resolve_transcript_path(data: Dict[str, Any]) -> Optional[str]:
    transcript_path = data.get("transcriptPath") or data.get("transcript_path")
    if not transcript_path and data.get("artifactDirectoryPath"):
        cand = os.path.join(
            str(data.get("artifactDirectoryPath")),
            ".system_generated",
            "logs",
            "transcript.jsonl",
        )
        if os.path.isfile(cand):
            transcript_path = cand
    return str(transcript_path) if transcript_path and isinstance(transcript_path, str) else None


def _extract_tc_name_args(tc: Any) -> Tuple[str, Dict[str, Any]]:
    if not isinstance(tc, dict):
        return "", {}
    tc_name = str(tc.get("name") or (tc.get("function") or {}).get("name") or "").strip()
    tc_args = tc.get("args") or tc.get("arguments") or (tc.get("function") or {}).get("arguments") or {}
    if isinstance(tc_args, str):
        try:
            tc_args = json.loads(tc_args)
        except Exception:
            tc_args = {}
    if not isinstance(tc_args, dict):
        tc_args = {}
    return tc_name, tc_args


def _extract_role_from_text(text: str) -> Optional[str]:
    if not text:
        return None
    for regex in (
        FORK_IDENTITY_LINE_REGEX,
        SWARM_WORKER_ROLE_REGEX,
        BOARD_ASSIGNMENT_FOR_ROLE_REGEX,
        BOARD_ASSIGNMENT_MENTION_REGEX,
    ):
        m = regex.search(text)
        if m:
            role = m.group(1).strip().lstrip("@").lower()
            if role:
                return role
    return None


def _iter_origin_messages(
    artifact_dir: Optional[str],
) -> List[Tuple[Dict[str, Any], str, Dict[str, Any], str]]:
    """
    Returns parsed (msg_data, tc_name, tc_args, msg_title) entries from
    `<artifact_dir>/.system_generated/messages`, skipping child send_message
    and non-parent peer messages.
    """
    if not artifact_dir or not isinstance(artifact_dir, str):
        return []
    messages_dir = os.path.join(artifact_dir, ".system_generated", "messages")
    results: List[Tuple[Dict[str, Any], str, Dict[str, Any], str]] = []
    for msg_data in MESSAGES_CACHE.get_messages(messages_dir):
        src_meta = msg_data.get("sourceMetadata") or {}
        tc = (src_meta.get("tool") or {}).get("toolCall") or {}
        tc_name, tc_args = _extract_tc_name_args(tc)
        if tc_name == "send_message":
            continue
        msg_title = str((msg_data.get("renderDetails") or {}).get("messageTitle") or "")
        if msg_title.startswith("Message from ") and msg_title != "Message from Parent Agent":
            continue
        results.append((msg_data, tc_name, tc_args, msg_title))
    return results


def _get_swarm_role(
    artifact_dir: Optional[str],
    transcript_path: Optional[str],
    payload: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Extracts the swarm roster name (e.g. 'planner', 'councillor', 'auditor')
    for a swarm worker from test hooks, messages/*.json, or transcript records.
    Returns None if this is not a swarm worker or no role name is detectable.
    """
    if payload and payload.get("_test_swarm_role"):
        role = str(payload["_test_swarm_role"]).strip().lstrip("@").lower()
        return role or None

    has_non_envelope_swarm_marker = False

    for msg_data, tc_name, tc_args, _ in _iter_origin_messages(artifact_dir):
        try:
            if tc_name == "swarm":
                has_non_envelope_swarm_marker = True
                swarm_name = str(tc_args.get("name") or "").strip().lstrip("@").lower()
                if swarm_name:
                    return swarm_name
            msg_content = str(msg_data.get("content") or msg_data.get("text") or "")
            if msg_content and not _is_incoming_message_envelope(msg_content):
                if (
                    FORK_NOTICE_REGEX.search(msg_content)
                    or FORK_ASSIGNMENT_LINE_REGEX.search(msg_content)
                    or FORK_IDENTITY_LINE_REGEX.search(msg_content)
                    or SWARM_WORKER_LINE_REGEX.search(msg_content)
                ):
                    has_non_envelope_swarm_marker = True
                role = _extract_role_from_text(msg_content)
                if role:
                    return role
        except Exception:
            continue

    if transcript_path and isinstance(transcript_path, str):
        try:
            records = TRANSCRIPT_CACHE.get_records(transcript_path)
            for rec in records:
                if not _is_system_message_record(rec):
                    continue
                content = str(rec.get("content") or "")
                if not content or _is_incoming_message_envelope(content):
                    continue
                if (
                    FORK_NOTICE_REGEX.search(content)
                    or FORK_ASSIGNMENT_LINE_REGEX.search(content)
                    or FORK_IDENTITY_LINE_REGEX.search(content)
                    or SWARM_WORKER_LINE_REGEX.search(content)
                ):
                    has_non_envelope_swarm_marker = True
                role = _extract_role_from_text(content)
                if role:
                    return role

            # Second pass for real swarm workers whose board assignment arrives in a [Message] envelope
            if has_non_envelope_swarm_marker:
                for rec in records:
                    source = rec.get("source")
                    step_type = rec.get("type")
                    if _is_system_message_record(rec) or source in ("USER_EXPLICIT", "USER_INPUT") or step_type == "USER_INPUT":
                        content = str(rec.get("content") or "")
                        role = _extract_role_from_text(content)
                        if role:
                            return role
        except Exception:
            pass

    return None


def _is_persistent_swarm_worker(
    data: Dict[str, Any],
    artifact_dir: Optional[str] = None,
    transcript_path: Optional[str] = None,
    swarm_role: Optional[str] = None,
) -> bool:
    """
    Returns True if the session is a persistent Swarm worker (e.g. @planner,
    @councillor, workspace='share'/'inherit' board worker) rather than a
    single-turn ephemeral invoke_subagent child.
    """
    if "_test_is_swarm_worker" in data:
        return bool(data["_test_is_swarm_worker"])
    if swarm_role:
        return True

    if transcript_path and isinstance(transcript_path, str):
        try:
            for rec in TRANSCRIPT_CACHE.get_records(transcript_path):
                if not _is_system_message_record(rec):
                    continue
                content = str(rec.get("content") or "")
                if not content or _is_incoming_message_envelope(content):
                    continue
                if (
                    FORK_NOTICE_REGEX.search(content)
                    or FORK_ASSIGNMENT_LINE_REGEX.search(content)
                    or FORK_IDENTITY_LINE_REGEX.search(content)
                    or SWARM_WORKER_LINE_REGEX.search(content)
                ):
                    return True
        except Exception:
            pass

    for msg_data, tc_name, _, _ in _iter_origin_messages(artifact_dir):
        try:
            if tc_name == "swarm":
                return True
            msg_content = str(msg_data.get("content") or msg_data.get("text") or "")
            if msg_content and not _is_incoming_message_envelope(msg_content):
                if (
                    FORK_NOTICE_REGEX.search(msg_content)
                    or FORK_ASSIGNMENT_LINE_REGEX.search(msg_content)
                    or FORK_IDENTITY_LINE_REGEX.search(msg_content)
                    or SWARM_WORKER_LINE_REGEX.search(msg_content)
                ):
                    return True
        except Exception:
            continue

    return False


def is_subagent_session(payload: Dict[str, Any]) -> bool:
    """
    Deterministically detects whether the executing session is a Subagent Worker
    or the Main Session Commander.
    """
    if "_test_is_subagent" in payload:
        return bool(payload["_test_is_subagent"])

    if payload.get("_test_is_swarm_worker") is True:
        return True

    if (
        "_test_is_read_only_subagent" in payload
        or "_test_is_mcp_only" in payload
        or "_test_subagent_steps" in payload
        or "_test_subagent_elapsed_sec" in payload
        or "_test_swarm_role" in payload
    ):
        return True

    transcript_path = _resolve_transcript_path(payload)
    if transcript_path:
        try:
            for record in TRANSCRIPT_CACHE.get_records(transcript_path):
                if not _is_system_message_record(record):
                    continue

                content = record.get("content", "")
                if not isinstance(content, str) or not content:
                    continue

                if _is_incoming_message_envelope(content):
                    continue

                if (
                    FORK_NOTICE_REGEX.search(content)
                    or FORK_ASSIGNMENT_LINE_REGEX.search(content)
                    or FORK_IDENTITY_LINE_REGEX.search(content)
                ):
                    return True

                if (
                    (SUBAGENT_MARKER_1 in content and SUBAGENT_MARKER_2 in content)
                    or SWARM_WORKER_LINE_REGEX.search(content)
                ):
                    return True
        except Exception:
            pass

    artifact_dir = payload.get("artifactDirectoryPath")
    for data, tool_call_name, _, msg_title in _iter_origin_messages(artifact_dir):
        try:
            if msg_title == "Message from Parent Agent":
                return True

            if tool_call_name in ("invoke_subagent", "swarm"):
                return True

            msg_content = str(data.get("content") or data.get("text") or "")
            if not msg_content or _is_incoming_message_envelope(msg_content):
                continue

            if (
                FORK_NOTICE_REGEX.search(msg_content)
                or FORK_ASSIGNMENT_LINE_REGEX.search(msg_content)
                or FORK_IDENTITY_LINE_REGEX.search(msg_content)
                or SWARM_WORKER_LINE_REGEX.search(msg_content)
                or (
                    SUBAGENT_MARKER_1 in msg_content
                    and SUBAGENT_MARKER_2 in msg_content
                )
            ):
                return True
        except Exception:
            continue

    return False


def _put_parent_id_cache(cache_key: str, parent_id: str) -> None:
    if not cache_key or not parent_id:
        return
    with _PARENT_ID_CACHE_LOCK:
        if (
            cache_key not in _PARENT_ID_CACHE
            and len(_PARENT_ID_CACHE) >= MAX_PARENT_ID_CACHE_ENTRIES
        ):
            oldest_key = next(iter(_PARENT_ID_CACHE))
            _PARENT_ID_CACHE.pop(oldest_key, None)
        _PARENT_ID_CACHE[cache_key] = parent_id


def _save_parent_id_cache(
    cache_key: str, curr_conv_id: str, brain_dir: str, parent_id: str
) -> None:
    if not parent_id or (curr_conv_id and parent_id.lower() == curr_conv_id.lower()):
        return
    _put_parent_id_cache(cache_key, parent_id)
    if brain_dir and curr_conv_id:
        sys_gen_dir = os.path.join(brain_dir, curr_conv_id, ".system_generated")
        if os.path.isdir(sys_gen_dir):
            cache_path = os.path.join(sys_gen_dir, ".parent_id_cache.json")
            tmp_path = f"{cache_path}.{os.getpid()}.{threading.get_ident()}.tmp"
            try:
                with open(tmp_path, "w", encoding="utf-8") as cf:
                    json.dump(
                        {"conversation_id": curr_conv_id, "parent_id": parent_id},
                        cf,
                        ensure_ascii=True,
                    )
                os.replace(tmp_path, cache_path)
            except Exception:
                try:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                except Exception:
                    pass


def _get_parent_conversation_id(
    curr_conv_id: str, brain_dir: str, payload: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """
    Resolves the parent conversation UUID for a subagent or swarm worker.
    """
    if payload and "_test_parent_conv_id" in payload:
        return str(payload["_test_parent_conv_id"])

    if not curr_conv_id:
        return None

    norm_brain = normalize_path(brain_dir) if brain_dir else ""
    if norm_brain:
        cache_key = f"{norm_brain}::{curr_conv_id.lower()}"
    else:
        tp_hint = normalize_path(str((payload or {}).get("transcriptPath") or ""))
        cache_key = f"tp:{tp_hint}::{curr_conv_id.lower()}" if tp_hint else ""

    if cache_key:
        with _PARENT_ID_CACHE_LOCK:
            cached = _PARENT_ID_CACHE.get(cache_key)
        if cached and cached.lower() != curr_conv_id.lower():
            return cached

    if brain_dir:
        disk_cache_path = os.path.join(
            brain_dir, curr_conv_id, ".system_generated", ".parent_id_cache.json"
        )
        if os.path.isfile(disk_cache_path):
            raw_cache = _read_text_with_retry(disk_cache_path)
            if raw_cache:
                try:
                    cache_data = json.loads(raw_cache)
                    if isinstance(cache_data, dict):
                        cached_pid = str(cache_data.get("parent_id") or "").strip()
                        cached_cid = str(cache_data.get("conversation_id") or "").strip()
                        if (
                            cached_pid
                            and cached_pid.lower() != curr_conv_id.lower()
                            and (not cached_cid or cached_cid.lower() == curr_conv_id.lower())
                        ):
                            _put_parent_id_cache(cache_key, cached_pid)
                            return cached_pid
                except Exception:
                    pass

    uuid_pattern = re.compile(
        r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}",
        re.IGNORECASE,
    )

    # 1. Scan current conversation transcript for parent pointer
    candidate_transcripts: List[str] = []
    if brain_dir:
        candidate_transcripts.append(
            os.path.join(brain_dir, curr_conv_id, ".system_generated", "logs", "transcript.jsonl")
        )
        candidate_transcripts.append(
            os.path.join(brain_dir, curr_conv_id, "transcript.jsonl")
        )
    if payload and payload.get("transcriptPath"):
        candidate_transcripts.append(str(payload["transcriptPath"]))

    seen_tp = set()
    for tp in candidate_transcripts:
        if not tp:
            continue
        norm_tp = normalize_path(tp)
        if norm_tp in seen_tp:
            continue
        seen_tp.add(norm_tp)
        records = TRANSCRIPT_CACHE.get_records(tp)
        if not records:
            continue
        try:
            found_swarm_sender = None
            fallback_sender = None
            for rec in records:
                has_role_fields = bool(rec.get("source") or rec.get("type"))
                if has_role_fields and not _is_system_message_record(rec):
                    continue
                rec_content = rec.get("content")
                if isinstance(rec_content, str):
                    search_text = rec_content[:16384]
                else:
                    search_text = json.dumps(rec, ensure_ascii=False)[:16384]

                is_envelope = _is_incoming_message_envelope(search_text)

                if not is_envelope:
                    m_fork = FORK_NOTICE_REGEX.search(search_text)
                    if m_fork:
                        fork_parent = m_fork.group(1)
                        if fork_parent.lower() != curr_conv_id.lower():
                            _save_parent_id_cache(
                                cache_key, curr_conv_id, brain_dir, fork_parent
                            )
                            return fork_parent

                    m_caller = re.search(
                        r'caller agent\s*\([^)]*id:\s*["\']([a-f0-9\-]{36})["\']',
                        search_text,
                        re.IGNORECASE,
                    )
                    if m_caller:
                        caller_parent = m_caller.group(1)
                        if caller_parent.lower() != curr_conv_id.lower():
                            _save_parent_id_cache(
                                cache_key, curr_conv_id, brain_dir, caller_parent
                            )
                            return caller_parent

                m2 = re.search(r"sender=([a-f0-9\-]{36})", search_text)
                if m2:
                    sender_val = m2.group(1)
                    if sender_val.lower() != curr_conv_id.lower():
                        if (
                            "[swarm] new board message" in search_text
                            or FORK_ASSIGNMENT_LINE_REGEX.search(search_text)
                            or "assignment (recorded on the board" in search_text
                        ):
                            found_swarm_sender = sender_val
                        elif not fallback_sender:
                            fallback_sender = sender_val

            if found_swarm_sender:
                _save_parent_id_cache(
                    cache_key, curr_conv_id, brain_dir, found_swarm_sender
                )
                return found_swarm_sender
            if fallback_sender:
                _save_parent_id_cache(
                    cache_key, curr_conv_id, brain_dir, fallback_sender
                )
                return fallback_sender
        except Exception:
            pass

    # 2. Check current conversation's .system_generated/messages/*.json
    if brain_dir:
        msgs_dir = os.path.join(brain_dir, curr_conv_id, ".system_generated", "messages")
        preferred_sender = None
        fallback_sender = None
        for mdata in MESSAGES_CACHE.get_messages(msgs_dir):
            try:
                src_meta = mdata.get("sourceMetadata") or {}
                tc_name = (
                    ((src_meta.get("tool") or {}).get("toolCall") or {}).get("name")
                )
                msg_title = str(
                    (mdata.get("renderDetails") or {}).get("messageTitle") or ""
                )
                if (
                    msg_title.startswith("Message from ")
                    and msg_title != "Message from Parent Agent"
                ):
                    continue
                sender = mdata.get("sender") or src_meta.get("sender")
                if sender and uuid_pattern.match(str(sender)):
                    sender_str = str(sender)
                    if sender_str.lower() != curr_conv_id.lower():
                        if tc_name in ("invoke_subagent", "swarm"):
                            preferred_sender = sender_str
                            break
                        if not fallback_sender:
                            fallback_sender = sender_str
            except Exception:
                continue
        chosen_sender = preferred_sender or fallback_sender
        if chosen_sender:
            _save_parent_id_cache(
                cache_key, curr_conv_id, brain_dir, chosen_sender
            )
            return chosen_sender

    # 3. Bounded, mtime-desc sorted sibling brain scan: find recent parent referencing curr_conv_id
    if brain_dir and os.path.isdir(brain_dir):
        try:
            candidates: List[Tuple[int, str, str]] = []
            curr_lower = curr_conv_id.lower()
            scan_start = time.monotonic()
            with os.scandir(brain_dir) as it:
                for entry in it:
                    if (
                        len(candidates) >= MAX_SIBLING_BRAIN_SCAN
                        and (time.monotonic() - scan_start) >= SIBLING_SCAN_TIME_BUDGET_SEC
                    ):
                        break
                    if entry.name.lower() == curr_lower:
                        continue
                    try:
                        if not entry.is_dir():
                            continue
                    except OSError:
                        continue
                    sibling_transcript = os.path.join(
                        entry.path, ".system_generated", "logs", "transcript.jsonl"
                    )
                    try:
                        st = os.stat(sibling_transcript)
                    except OSError:
                        continue
                    if stat.S_ISREG(st.st_mode):
                        candidates.append((st.st_mtime_ns, entry.name, sibling_transcript))

            candidates.sort(key=lambda item: item[0], reverse=True)
            for _, sibling_id, sibling_transcript in candidates[:MAX_SIBLING_BRAIN_SCAN]:
                if (time.monotonic() - scan_start) >= SIBLING_SCAN_TIME_BUDGET_SEC:
                    break
                sample = _read_text_with_retry(sibling_transcript, max_bytes=65536)
                if sample and curr_lower in sample.lower():
                    _save_parent_id_cache(
                        cache_key, curr_conv_id, brain_dir, sibling_id
                    )
                    return sibling_id
        except Exception:
            pass

    return None


def _is_valid_parent_artifact_access(
    target_conv_id: str,
    curr_conv_id: Optional[str],
    brain_dir: Optional[str],
    payload: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Returns True ONLY if target_conv_id matches curr_conv_id, the resolved parent
    conversation ID, or an explicit _test_valid_parent_ids entry.
    """
    if not target_conv_id:
        return False
    target_lower = target_conv_id.lower()
    if curr_conv_id and target_lower == curr_conv_id.lower():
        return True

    if payload and isinstance(payload.get("_test_valid_parent_ids"), (list, tuple, set)):
        valid_ids = {str(item).lower() for item in payload["_test_valid_parent_ids"] if item}
        if target_lower in valid_ids:
            return True

    parent_id = _get_parent_conversation_id(curr_conv_id or "", brain_dir or "", payload)
    if parent_id and target_lower == parent_id.lower():
        return True

    return False


def _detect_read_only_from_messages_or_first_prompt(
    artifact_dir: Optional[str],
    transcript_path: Optional[str],
    swarm_role: Optional[str] = None,
) -> bool:
    """
    Deterministically checks whether a subagent was invoked with TypeName='research',
    an explicit Phase 0 Read-Only prompt, or a read-only swarm role (@councillor, or
    read-only flagged @auditor), WITHOUT matching global <user_rules> or <subagents>
    descriptions inside the system prompt header.
    """
    role_norm = (swarm_role or "").strip().lstrip("@").lower()
    if role_norm == "councillor" or role_norm.startswith("councillor-"):
        return True

    is_auditor_role = role_norm == "auditor" or role_norm.startswith("auditor-")

    # 1. Check .system_generated/messages/*.json for invoke_subagent TypeName or swarm RO flags
    if artifact_dir and isinstance(artifact_dir, str):
        messages_dir = os.path.join(artifact_dir, ".system_generated", "messages")
        for msg_data in MESSAGES_CACHE.get_messages(messages_dir):
            try:
                src_meta = msg_data.get("sourceMetadata") or {}
                tc = (src_meta.get("tool") or {}).get("toolCall") or {}
                tc_name, tc_args = _extract_tc_name_args(tc)
                if tc_name == "invoke_subagent":
                    t_name = str(tc_args.get("TypeName") or "").strip().lower()
                    if t_name == "research":
                        return True
                    if t_name == "self":
                        return False
                if is_auditor_role:
                    brief_text = str(tc_args.get("brief") or "") if tc_name == "swarm" else ""
                    msg_text = str(msg_data.get("content") or msg_data.get("text") or "")
                    if AUDITOR_RO_FLAG_REGEX.search(brief_text) or AUDITOR_RO_FLAG_REGEX.search(msg_text):
                        return True
            except Exception:
                continue

    # 2. Check ONLY the first USER_INPUT / USER_EXPLICIT step (or assignment for @auditor) in transcript.jsonl
    if transcript_path and isinstance(transcript_path, str):
        try:
            for rec in TRANSCRIPT_CACHE.get_records(transcript_path):
                source = rec.get("source")
                step_type = rec.get("type")
                content = str(rec.get("content") or "")
                if is_auditor_role and (_is_system_message_record(rec) or source in ("USER_EXPLICIT", "USER_INPUT") or step_type == "USER_INPUT"):
                    if FORK_ASSIGNMENT_MARKER in content or not _is_incoming_message_envelope(content):
                        if AUDITOR_RO_FLAG_REGEX.search(content):
                            return True
                if source in ("USER_EXPLICIT", "USER_INPUT") or step_type == "USER_INPUT":
                    first_prompt = content[:300]
                    if re.search(
                        r"(you are a (phase 0 )?read-only reconnaissance subagent|do not modify any files)",
                        first_prompt,
                        re.IGNORECASE,
                    ):
                        return True
                    if not is_auditor_role:
                        break
        except Exception:
            pass

    return False


def _detect_mcp_only_from_messages_or_first_prompt(
    artifact_dir: Optional[str], transcript_path: Optional[str]
) -> bool:
    """
    Checks whether a subagent was invoked with [MCP_ONLY] in its Role or Prompt.
    """
    # 1. Check .system_generated/messages/*.json for invoke_subagent args
    for msg_data, tc_name, tc_args, _ in _iter_origin_messages(artifact_dir):
        try:
            if tc_name == "invoke_subagent":
                role_text = str(tc_args.get("Role") or "")
                prompt_text = str(tc_args.get("Prompt") or "")
                if "[mcp_only]" in role_text.lower() or "[mcp_only]" in prompt_text.lower():
                    return True
            raw_msg_text = str(msg_data.get("content") or msg_data.get("text") or "")
            if "[mcp_only]" in raw_msg_text.lower():
                return True
        except Exception:
            continue

    # 2. Check transcript.jsonl first prompt or system message
    if transcript_path and isinstance(transcript_path, str):
        try:
            for rec in TRANSCRIPT_CACHE.get_records(transcript_path):
                source = rec.get("source")
                step_type = rec.get("type")
                content = str(rec.get("content") or "")
                if _is_incoming_message_envelope(content):
                    continue
                if (
                    source in ("USER_EXPLICIT", "USER_INPUT")
                    or (step_type == "USER_INPUT" and source != "SYSTEM")
                    or (_is_system_message_record(rec) and rec.get("step_index") == 0)
                ):
                    if "[mcp_only]" in content.lower():
                        return True
                    break
        except Exception:
            pass

    return False


def _is_429_error_record(record: Dict[str, Any]) -> bool:
    if not isinstance(record, dict):
        return False
    step_type = str(record.get("type") or "").upper()
    status = str(record.get("status") or "").upper()
    if step_type == "ERROR_MESSAGE" or status == "ERROR":
        err_text = " ".join(
            str(record.get(k) or "")
            for k in ("content", "error", "message", "errorMessage")
            if record.get(k)
        )
        if RETRY_429_REGEX.search(err_text):
            return True
    return False


def get_subagent_profile(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyzes the subagent / swarm worker session to determine:
    - is_subagent: bool
    - is_read_only: bool
    - is_mcp_only: bool
    - steps_since_last_prompt: int
    - elapsed_seconds: float (active turn seconds excluding 429 retry gaps)
    - is_swarm_worker: bool (when is_subagent is True)
    - swarm_role: Optional[str] (when is_subagent is True)
    """
    if not is_subagent_session(data):
        return {
            "is_subagent": False,
            "is_read_only": False,
            "is_mcp_only": False,
            "steps_since_last_prompt": 0,
            "elapsed_seconds": 0.0,
        }

    transcript_path = _resolve_transcript_path(data)
    artifact_dir = data.get("artifactDirectoryPath")
    swarm_role = _get_swarm_role(artifact_dir, transcript_path, data)
    is_swarm_worker = _is_persistent_swarm_worker(
        data, artifact_dir, transcript_path, swarm_role=swarm_role
    )

    if "_test_is_read_only_subagent" in data:
        is_read_only = bool(data["_test_is_read_only_subagent"])
    else:
        is_read_only = _detect_read_only_from_messages_or_first_prompt(
            artifact_dir, transcript_path, swarm_role=swarm_role
        )

    if "_test_is_mcp_only" in data:
        is_mcp_only = bool(data["_test_is_mcp_only"])
    else:
        is_mcp_only = _detect_mcp_only_from_messages_or_first_prompt(
            artifact_dir, transcript_path
        )

    steps_since_last_prompt = int(data.get("_test_subagent_steps", 0))
    elapsed_seconds = float(data.get("_test_subagent_elapsed_sec", 0.0))

    need_steps = "_test_subagent_steps" not in data
    need_elapsed = "_test_subagent_elapsed_sec" not in data

    if (
        (need_steps or need_elapsed)
        and transcript_path
        and isinstance(transcript_path, str)
    ):
        try:
            current_turn_start_time = None
            step_count = 0
            retry_gap_seconds = 0.0
            pending_429_dt: Optional[datetime] = None

            _UNRESOLVED = object()
            parent_id_for_wrap: Any = _UNRESOLVED

            def _resolve_parent_id_lazy() -> Optional[str]:
                nonlocal parent_id_for_wrap
                if parent_id_for_wrap is _UNRESOLVED:
                    curr_cid = data.get("conversationId") or (
                        _path_basename(artifact_dir) if artifact_dir else ""
                    )
                    b_dir = _path_dirname(artifact_dir) if artifact_dir else ""
                    parent_id_for_wrap = (
                        _get_parent_conversation_id(curr_cid, b_dir, data)
                        if curr_cid
                        else None
                    )
                return parent_id_for_wrap

            for record in TRANSCRIPT_CACHE.get_records(transcript_path):
                source = record.get("source")
                step_type = record.get("type")
                created_at = record.get("created_at")
                content = str(record.get("content") or "")

                if _is_429_error_record(record):
                    if current_turn_start_time and pending_429_dt is None:
                        pending_429_dt = _parse_iso_ts(created_at)
                    continue

                if pending_429_dt is not None:
                    next_dt = _parse_iso_ts(created_at)
                    if next_dt is not None:
                        retry_gap_seconds += max(0.0, (next_dt - pending_429_dt).total_seconds())
                        pending_429_dt = None

                if (
                    _is_system_message_record(record)
                    and not _is_incoming_message_envelope(content)
                    and (
                        FORK_NOTICE_REGEX.search(content)
                        or FORK_ASSIGNMENT_LINE_REGEX.search(content)
                        or FORK_IDENTITY_LINE_REGEX.search(content)
                    )
                ):
                    step_count = 0
                    current_turn_start_time = created_at
                    retry_gap_seconds = 0.0
                    pending_429_dt = None
                    continue

                is_prompt = False
                is_wrap_up = False
                if _is_system_message_record(record):
                    is_parent_directive = False
                    if "Message from Parent Agent" in content:
                        is_parent_directive = True
                    elif (
                        len(content) < 350
                        and "[Message]" in content
                        and "sender=" in content
                        and FORK_ASSIGNMENT_MARKER not in content
                        and "[swarm] new board message" not in content
                        and WRAP_UP_REGEX.search(content)
                    ):
                        content_lower = content.lower()
                        if "sender=parent" in content_lower:
                            is_parent_directive = True
                        else:
                            resolved_pid = _resolve_parent_id_lazy()
                            if (
                                not resolved_pid
                                or f"sender={resolved_pid.lower()}" in content_lower
                            ):
                                is_parent_directive = True

                    if is_parent_directive and len(content) < 350 and WRAP_UP_REGEX.search(content):
                        is_wrap_up = True
                    elif (
                        "[Message]" in content
                        or "sender=" in content
                        or "Message from Parent Agent" in content
                        or "[swarm] new board message" in content
                    ):
                        is_prompt = True
                elif source in ("USER_EXPLICIT", "USER_INPUT") or step_type == "USER_INPUT":
                    is_prompt = True

                if is_wrap_up:
                    step_count = 999
                elif is_prompt:
                    step_count = 0
                    if created_at:
                        current_turn_start_time = created_at
                    retry_gap_seconds = 0.0
                    pending_429_dt = None
                else:
                    if source == "MODEL" or step_type == "PLANNER_RESPONSE":
                        tcs = record.get("tool_calls")
                        if tcs and isinstance(tcs, (list, dict)) and len(tcs) > 0:
                            tc_list = tcs if isinstance(tcs, list) else [tcs]
                            active_tcs = [
                                tc for tc in tc_list
                                if isinstance(tc, dict)
                                and _extract_tc_name_args(tc)[0].lower() not in PASSIVE_SWARM_SYNC_TOOLS
                            ]
                            if active_tcs:
                                step_count += 1
                            if not current_turn_start_time and created_at:
                                current_turn_start_time = created_at

            if need_steps:
                steps_since_last_prompt = step_count

            if need_elapsed and current_turn_start_time:
                dt = _parse_iso_ts(current_turn_start_time)
                if dt is not None:
                    now = datetime.now(timezone.utc)
                    if pending_429_dt is not None:
                        retry_gap_seconds += max(0.0, (now - pending_429_dt).total_seconds())
                    raw_elapsed = max(0.0, (now - dt).total_seconds())
                    elapsed_seconds = max(0.0, raw_elapsed - retry_gap_seconds)
        except Exception:
            pass

    return {
        "is_subagent": True,
        "is_read_only": is_read_only,
        "is_mcp_only": is_mcp_only,
        "steps_since_last_prompt": steps_since_last_prompt,
        "elapsed_seconds": elapsed_seconds,
        "is_swarm_worker": is_swarm_worker,
        "swarm_role": swarm_role,
    }


def inspect_target_subagent(recipient: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Inspects a target subagent transcript/messages to determine:
    - is_read_only: bool
    - has_completed_turn: bool
    - total_model_tool_steps: int
    - last_message_content: str
    """
    is_read_only = bool(
        payload.get("_test_target_is_read_only", False)
        or payload.get("_test_target_is_readonly", False)
    )
    has_completed_turn = bool(payload.get("_test_target_completed", False))
    total_model_tool_steps = int(payload.get("_test_target_steps", 0))
    last_message_content = str(payload.get("_test_target_last_message", ""))

    target_transcript_path = payload.get("_test_target_transcript_path")
    target_artifact_dir = None
    if not target_transcript_path:
        artifact_dir = payload.get("artifactDirectoryPath")
        if artifact_dir and isinstance(artifact_dir, str):
            brain_root = _path_dirname(artifact_dir)
        else:
            brain_root = os.path.expanduser("~/.gemini/antigravity/brain")
        target_artifact_dir = os.path.join(brain_root, recipient)
        target_transcript_path = os.path.join(
            target_artifact_dir, ".system_generated", "logs", "transcript.jsonl"
        )

    if "_test_target_is_read_only" not in payload:
        is_read_only = _detect_read_only_from_messages_or_first_prompt(
            target_artifact_dir, target_transcript_path
        )

    if target_transcript_path and isinstance(target_transcript_path, str):
        try:
            records = TRANSCRIPT_CACHE.get_records(target_transcript_path)
            if records:
                computed_steps = 0
                computed_completed = False
                last_msg = ""

                for step in records:
                    source = step.get("source")
                    step_type = step.get("type")
                    tcs = step.get("tool_calls") or []
                    content = str(step.get("content") or "")

                    if source == "MODEL" or step_type == "PLANNER_RESPONSE":
                        tc_list = tcs if isinstance(tcs, list) else ([tcs] if isinstance(tcs, dict) else [])
                        if len(tc_list) == 0:
                            computed_completed = True
                            if content:
                                last_msg = content
                        else:
                            active_tcs = [
                                tc for tc in tc_list
                                if isinstance(tc, dict)
                                and _extract_tc_name_args(tc)[0].lower() not in PASSIVE_SWARM_SYNC_TOOLS
                            ]
                            if active_tcs:
                                computed_steps += 1
                            for tc in tc_list:
                                tc_name, tc_args = _extract_tc_name_args(tc)
                                if tc_name == "send_message":
                                    computed_completed = True
                                    if "Message" in tc_args:
                                        last_msg = str(tc_args["Message"])
                                elif content:
                                    last_msg = content

                if "_test_target_completed" not in payload:
                    has_completed_turn = computed_completed
                if "_test_target_steps" not in payload:
                    total_model_tool_steps = computed_steps
                if "_test_target_last_message" not in payload and last_msg:
                    last_message_content = last_msg

        except Exception:
            pass

    return {
        "is_read_only": is_read_only,
        "has_completed_turn": has_completed_turn,
        "total_model_tool_steps": total_model_tool_steps,
        "last_message_content": last_message_content,
    }


def _inspect_parent_escalation_state(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Scans the Main Session transcript tail to track consecutive invoke_subagent
    retries after STATUS: ESCALATE_REQUIRED, CIRCUIT BREAKER, NO_VALID_SEND, or
    retry keywords without an intervening @councillor strategy or ask_question.
    """
    if "_test_retry_streak" in payload:
        return {
            "retry_streak": int(payload.get("_test_retry_streak", 0)),
            "councillor_tier": payload.get("_test_councillor_tier"),
            "escalation_pending": bool(payload.get("_test_escalation_pending", False)),
        }

    transcript_path = _resolve_transcript_path(payload)
    if not transcript_path:
        return {
            "retry_streak": 0,
            "councillor_tier": None,
            "escalation_pending": False,
        }

    records = TRANSCRIPT_CACHE.get_records(transcript_path)
    if not records:
        return {
            "retry_streak": 0,
            "councillor_tier": None,
            "escalation_pending": False,
        }

    tail = records[-150:]
    retry_streak = 0
    escalation_pending = False
    councillor_tier: Optional[str] = None
    councillor_consulted = False

    for rec in tail:
        source = rec.get("source")
        step_type = rec.get("type")
        content = str(rec.get("content") or "")

        if (
            step_type == "TOOL_RESPONSE"
            or _is_system_message_record(rec)
            or step_type == "USER_INPUT"
            or source in ("USER_EXPLICIT", "USER_INPUT")
        ):
            tool_name_resp = str(rec.get("tool_name") or "").lower()
            if tool_name_resp == "ask_question":
                retry_streak = 0
                escalation_pending = False
                councillor_tier = None
                councillor_consulted = False
                continue

            if councillor_consulted and (
                (
                    tool_name_resp == "read_board"
                    and re.search(r'"agent"\s*:\s*"councillor[^"]*"', content, re.IGNORECASE)
                )
                or (
                    "[Message]" in content
                    and re.search(
                        r"(?:@?councillor\b[\s\S]{0,2000}?(?:STATUS:|STRATEGY:|RECOMMENDATION:)|from\s+@?councillor\b)",
                        content[:16384],
                        re.IGNORECASE,
                    )
                )
            ):
                retry_streak = 0
                escalation_pending = False
                councillor_consulted = False
                continue

            if (
                step_type == "TOOL_RESPONSE"
                or _is_incoming_message_envelope(content)
                or _is_system_message_record(rec)
            ):
                if ESCALATION_CUE_REGEX.search(content):
                    escalation_pending = True
                elif "STATUS: COMPLETED" in content.upper() and _is_incoming_message_envelope(content):
                    escalation_pending = False

        if source == "MODEL" or step_type == "PLANNER_RESPONSE":
            tcs = rec.get("tool_calls") or []
            if isinstance(tcs, dict):
                tcs = [tcs]
            if not isinstance(tcs, list):
                continue
            for tc in tcs:
                tc_name, tc_args = _extract_tc_name_args(tc)
                tc_lower = tc_name.lower()
                if tc_lower == "swarm":
                    action = str(tc_args.get("action") or "").lower()
                    name = str(tc_args.get("name") or "").strip().lstrip("@").lower()
                    model = str(tc_args.get("model") or "").lower()
                    if name == "councillor" or name.startswith("councillor-"):
                        if action == "add":
                            councillor_tier = "carbon" if "carbon" in model else "neon"
                            councillor_consulted = True
                        elif action == "model" and "carbon" in model:
                            councillor_tier = "carbon"
                            councillor_consulted = True
                elif tc_lower == "post_message":
                    text = str(tc_args.get("text") or tc_args.get("Message") or "")
                    if "@councillor" in text.lower():
                        councillor_consulted = True
                elif tc_lower == "ask_question":
                    retry_streak = 0
                    escalation_pending = False
                    councillor_tier = None
                    councillor_consulted = False
                elif tc_lower == "invoke_subagent":
                    role = str(tc_args.get("Role") or tc_args.get("role") or "")
                    prompt = str(tc_args.get("Prompt") or tc_args.get("prompt") or "")
                    is_retry = bool(
                        RETRY_KEYWORD_REGEX.search(role)
                        or RETRY_KEYWORD_REGEX.search(prompt[:600])
                    )
                    if escalation_pending or is_retry:
                        retry_streak += 1
                    else:
                        retry_streak = 0

    return {
        "retry_streak": retry_streak,
        "councillor_tier": councillor_tier,
        "escalation_pending": escalation_pending,
    }


def evaluate_pre_tool_use(payload: Dict[str, Any]) -> Dict[str, Any]:
    tool_call = payload.get("toolCall") or {}
    tool_name = str(tool_call.get("name") or "").strip()
    tool_lower = tool_name.lower()
    args = tool_call.get("args") or {}
    if not isinstance(args, dict):
        args = {}

    artifact_dir = payload.get("artifactDirectoryPath")

    if tool_lower == "swarm":
        banned_model_res = _check_banned_swarm_model(args)
        if banned_model_res is not None:
            return banned_model_res

    subagent_active = is_subagent_session(payload)

    # =========================================================================
    # A. Subagent Session — Worker Boundary
    # =========================================================================
    if subagent_active:
        if tool_lower == "ask_question":
            return {
                "decision": "deny",
                "reason": (
                    "[Orchestrator Guard] Subagents must NOT call 'ask_question' directly. "
                    "Immediately stop and return STATUS: CLARIFICATION_NEEDED with your question "
                    "and recommended options to the Main Session so the Main Session can grill the user via ask_question."
                ),
            }

        if tool_lower == "send_message":
            msg = str(args.get("Message") or args.get("message") or "")
            if len(msg) > MAX_RETURN_MESSAGE_CHARS:
                return {
                    "decision": "deny",
                    "reason": (
                        f"ORCHESTRATOR GUARD BLOCKED: Subagent return message exceeds 2,500 characters ({len(msg)} chars). "
                        "Never dump raw code blocks or JSON logs into Main Session messages. "
                        "Write large outputs to <artifactDirectoryPath>/scratch/ and return a compact summary (< 2,500 chars) with file paths and line numbers."
                    ),
                }

        profile = get_subagent_profile(payload)
        is_read_only = profile["is_read_only"]
        is_mcp_only = profile.get("is_mcp_only", False)
        is_swarm_worker = profile.get("is_swarm_worker", False)
        steps = profile["steps_since_last_prompt"]
        elapsed_sec = profile["elapsed_seconds"]

        # [MCP_ONLY] Execution Mode Enforcement
        if is_mcp_only and (tool_lower == "run_command" or tool_lower in WRITE_FILE_TOOLS):
            return {
                "decision": "deny",
                "reason": (
                    "ORCHESTRATOR GUARD: This worker is locked to [MCP_ONLY] mode. "
                    "Shell commands (run_command) and file edits are strictly forbidden. "
                    "Call the target MCP tool directly via call_mcp_tool and finish."
                ),
            }

        # Block Reading Stale Scratch / Plan / Kanban Directories from Past Conversations
        curr_conv_id = payload.get("conversationId")
        if not curr_conv_id and artifact_dir:
            curr_conv_id = _path_basename(artifact_dir)

        brain_dir = _path_dirname(artifact_dir) if artifact_dir else None
        if not brain_dir and payload.get("appDataDir"):
            brain_dir = os.path.join(str(payload.get("appDataDir")), "brain")

        stale_scratch_detected = False
        target_path = ""
        norm_target = ""
        cmd = ""
        norm_cmd = ""
        if tool_lower in READ_FILE_TOOLS or tool_lower in WRITE_FILE_TOOLS:
            target_path = extract_target_path(args) or ""
            norm_target = normalize_path(target_path)
            m = BRAIN_ARTIFACT_PATH_REGEX.search(norm_target)
            if m:
                matched_id = m.group(1)
                if not _is_valid_parent_artifact_access(matched_id, curr_conv_id, brain_dir, payload):
                    stale_scratch_detected = True
        elif tool_lower == "run_command":
            cmd = str(args.get("CommandLine") or "")
            norm_cmd = cmd.replace("\\", "/")
            m = BRAIN_ARTIFACT_CMD_REGEX.search(norm_cmd)
            if m:
                matched_id = m.group(1)
                if not _is_valid_parent_artifact_access(matched_id, curr_conv_id, brain_dir, payload):
                    stale_scratch_detected = True

        if stale_scratch_detected:
            return {
                "decision": "deny",
                "reason": (
                    "ORCHESTRATOR GUARD: Reading or executing from stale scratch directories of past conversations is strictly forbidden. "
                    "Access files directly from the active workspace repository or your current/parent conversation's scratch, plan, or kanban artifacts."
                ),
            }

        # Enforce @planner-only write authority on implementation_plan.md and kanban/**
        swarm_role = profile.get("swarm_role")
        if not _is_planner_role(swarm_role):
            planner_only_deny = False
            if tool_lower in WRITE_FILE_TOOLS and PLANNER_ONLY_ARTIFACT_PATH_REGEX.search(norm_target):
                planner_only_deny = True
            elif tool_lower == "run_command" and PLANNER_ONLY_ARTIFACT_CMD_REGEX.search(norm_cmd):
                if READ_ONLY_CMD_BLOCK_REGEX.search(cmd) or PLANNER_ONLY_CMD_REDIRECT_REGEX.search(norm_cmd):
                    planner_only_deny = True

            if planner_only_deny:
                return {
                    "decision": "deny",
                    "reason": (
                        "ORCHESTRATOR GUARD BLOCKED (v2.0.0): Only the dedicated @planner Swarm worker may write or edit "
                        "implementation_plan.md or kanban/ artifacts. Non-@planner workers have read-only access to the parent plan and Kanban cards; "
                        "write dynamic outputs to <parentArtifactDirectoryPath>/scratch/ or your own scratch directory instead."
                    ),
                }

        # Step & Active-Time Circuit Breaker with Graceful Hand-Off
        if is_swarm_worker:
            max_steps = SWARM_RO_MAX_STEPS if is_read_only else SWARM_RW_MAX_STEPS
            max_seconds = None
        else:
            max_steps = SUBAGENT_RO_MAX_STEPS if is_read_only else SUBAGENT_RW_MAX_STEPS
            max_seconds = SUBAGENT_RO_MAX_SECONDS if is_read_only else SUBAGENT_RW_MAX_SECONDS

        if steps >= max_steps or (max_seconds is not None and elapsed_sec >= max_seconds):
            if tool_lower in CIRCUIT_BREAKER_EXEMPT_TOOLS:
                return {"decision": "allow"}
            if is_swarm_worker:
                cb_reason = (
                    "CIRCUIT BREAKER (Turn Budget Reached): Stop workspace/file/shell work now. "
                    "You MUST immediately call post_message with STATUS: COMPLETED or STATUS: ESCALATE_REQUIRED "
                    "summarizing progress and remaining items, then idle with swarm_wait. "
                    "Only post_message, read_board, swarm_wait, and send_message are permitted."
                )
            else:
                cb_reason = (
                    "CIRCUIT BREAKER (Turn Budget Reached): Stop workspace/file/shell work now. "
                    "You MUST immediately call send_message (for invoke_subagent) or post_message (for Swarm) "
                    "with STATUS: COMPLETED or STATUS: ESCALATE_REQUIRED summarizing progress and remaining items. "
                    "Only send_message, post_message, read_board, and swarm_wait are permitted."
                )
            return {
                "decision": "deny",
                "reason": cb_reason,
            }

        # Hard Read-Only Enforcement for Read-Only (research / Phase 0 / @councillor / RO @auditor)
        if is_read_only:
            if tool_lower in WRITE_FILE_TOOLS:
                return {
                    "decision": "deny",
                    "reason": (
                        f"[Orchestrator Guard] Read-Only workers/subagents are prohibited from writing or editing files ('{tool_name}'). "
                        "Phase 0 / Research / @councillor sessions are strictly read-only."
                    ),
                }

            is_mutating_mcp = _is_state_modifying_mcp_tool(tool_lower)
            if tool_lower == "call_mcp_tool":
                inner_tool = str(args.get("ToolName") or "").strip().lower()
                if _is_state_modifying_mcp_tool(inner_tool):
                    is_mutating_mcp = True

            if is_mutating_mcp:
                return {
                    "decision": "deny",
                    "reason": (
                        f"[Orchestrator Guard] Read-Only workers/subagents are prohibited from invoking state-modifying MCP tool '{tool_name}'. "
                        "Phase 0 / Research / @councillor sessions are strictly read-only."
                    ),
                }

            if tool_lower == "run_command":
                cmd = str(args.get("CommandLine") or "")
                if READ_ONLY_CMD_BLOCK_REGEX.search(cmd):
                    return {
                        "decision": "deny",
                        "reason": (
                            f"[Orchestrator Guard] Read-Only workers/subagents are prohibited from executing state-modifying terminal command: '{cmd}'. "
                            "Phase 0 / Research / @councillor sessions are strictly read-only."
                        ),
                    }

        return {"decision": "allow"}

    # =========================================================================
    # B. Main Session — Pure Dispatcher Boundary
    # =========================================================================

    if tool_lower == "invoke_subagent":
        prompt_raw = str(args.get("Prompt") or args.get("prompt") or "")
        if len(prompt_raw) > MAX_SUBAGENT_PROMPT_CHARS:
            return {
                "decision": "deny",
                "reason": (
                    f"ORCHESTRATOR GUARD BLOCKED: invoke_subagent Prompt exceeds 3,500 characters ({len(prompt_raw)} chars). "
                    "Do NOT paste large code skeletons, file dumps, or duplicated specs into subagent prompts. "
                    "Delegate plan specs and worker cards via @planner to <artifactDirectoryPath>/implementation_plan.md and "
                    "<artifactDirectoryPath>/kanban/WP-*.md (or write scratch notes to <artifactDirectoryPath>/scratch/) and pass a concise file path + line-range pointer."
                ),
            }

        type_name = str(args.get("TypeName") or args.get("typeName") or "").strip().lower()
        role = str(args.get("Role") or args.get("role") or "")
        matched = detect_recon_invocation(role, prompt_raw)
        if (type_name == "self" or not type_name) and matched:
            return {
                "decision": "deny",
                "reason": (
                    f"ORCHESTRATOR GUARD: Phase 0 / Read-Only Reconnaissance subagents MUST be "
                    f"invoked with TypeName='research' (never TypeName='self') to enforce read-only isolation "
                    f"(matched='{matched}')."
                ),
            }

        esc_state = _inspect_parent_escalation_state(payload)
        if esc_state["retry_streak"] >= 2:
            tier = esc_state.get("councillor_tier")
            if tier == "neon":
                reason = (
                    "ORCHESTRATOR ESCALATION GATE (v2.0.0): Blocked after >= 2 consecutive invoke_subagent retries "
                    "following Tier-1 Neon @councillor consultation. Upgrade @councillor in-place to Tier-2 Carbon via "
                    "swarm(action='model', name='councillor', model='gemini-4-carbon-high') and post_message('@councillor ...') "
                    "+ swarm_wait(), or call ask_question to escalate to the user."
                )
            elif tier == "carbon":
                reason = (
                    "ORCHESTRATOR ESCALATION GATE (v2.0.0): Blocked after >= 2 consecutive invoke_subagent retries "
                    "even after Tier-2 Carbon @councillor consultation. Call ask_question now to align with the user "
                    "before dispatching additional invoke_subagent retries."
                )
            else:
                reason = (
                    "ORCHESTRATOR ESCALATION GATE (v2.0.0): Blocked after >= 2 consecutive invoke_subagent retries "
                    "without resolving the deadlock. Consult Tier-1 @councillor (Neon) first via "
                    "swarm(action='add', name='councillor', model='gemini-4-neon-high', fork='coordinator', brief='...') "
                    "+ swarm_wait(), or call ask_question. Retries resume once @councillor posts a strategy or ask_question is answered."
                )
            return {"decision": "deny", "reason": reason}

        return {"decision": "allow"}

    if tool_lower == "send_message":
        recipient = str(args.get("Recipient") or args.get("recipient") or "").strip()
        message = str(args.get("Message") or args.get("message") or "")

        target_profile = inspect_target_subagent(recipient, payload)

        if target_profile.get("is_read_only") or target_profile.get("is_readonly"):
            return {
                "decision": "deny",
                "reason": (
                    "ORCHESTRATOR GUARD BLOCKED: send_message to a TypeName='research' subagent is strictly prohibited (1 Task = 1 Subagent). "
                    "Research scouts are single-shot probes; terminate completed scouts via manage_subagents(Action='kill') "
                    "and never use them for multi-turn code/file paging."
                ),
            }

        if len(message) < 220 and WRAP_UP_REGEX.search(message):
            return {"decision": "allow"}

        if not target_profile["is_read_only"]:
            if target_profile["total_model_tool_steps"] >= 45:
                if "STATUS: CLARIFICATION_NEEDED" not in target_profile["last_message_content"]:
                    return {
                        "decision": "deny",
                        "reason": (
                            "ANTI-RECYCLING GUARD: Target subagent has already accumulated >= 45 active steps. "
                            "To prevent context degradation, kill this subagent via manage_subagents(Action='kill') "
                            "and spawn a fresh subagent or persistent Swarm worker for the new task."
                        ),
                    }

        return {"decision": "allow"}

    if tool_lower in ALLOWED_ORCHESTRATION_TOOLS:
        return {"decision": "allow"}

    if tool_lower in WRITE_FILE_TOOLS:
        target_path = extract_target_path(args) or ""
        norm_target = normalize_path(target_path)

        if target_path and artifact_dir:
            scratch_dir = os.path.join(artifact_dir, "scratch")
            if is_inside_directory(target_path, scratch_dir):
                return {"decision": "allow"}

        if (
            norm_target.endswith("/implementation_plan.md")
            or _path_basename(norm_target).lower() == "implementation_plan.md"
        ):
            return {
                "decision": "deny",
                "reason": (
                    "ORCHESTRATOR GUARD BLOCKED (v2.0.0): Main Session is prohibited from directly writing or editing implementation_plan.md. "
                    "Delegate plan authoring to the dedicated Neon @planner worker via "
                    "swarm(action='add', name='planner', model='gemini-4-neon-high', fork='coordinator', brief='...') "
                    "(or 'gemini-4-neon-medium' for single-WP tasks) and swarm_wait()."
                ),
            }

        is_kanban_target = False
        if target_path and artifact_dir:
            kanban_dir = os.path.join(artifact_dir, "kanban")
            if is_inside_directory(target_path, kanban_dir):
                is_kanban_target = True
        if not is_kanban_target and re.search(r"/brain/[^/]+/kanban(?:/|$)", norm_target, re.IGNORECASE):
            is_kanban_target = True

        if is_kanban_target:
            return {
                "decision": "deny",
                "reason": (
                    "ORCHESTRATOR GUARD BLOCKED (v2.0.0): Main Session is prohibited from directly writing or editing kanban/ planning artifacts. "
                    "Delegate Kanban board and worker card authoring to @planner via "
                    "post_message('@planner ...') or swarm(action='add', name='planner', ...) and swarm_wait()."
                ),
            }

        return {
            "decision": "deny",
            "reason": (
                f"[Orchestrator Pure-Dispatcher Guard] Main Session is restricted from modifying files outside scratch/ ('{target_path or 'unknown'}'). "
                "The Main Session is a strictly Pure Dispatcher and may only write scratch files inside "
                f"'{os.path.join(artifact_dir, 'scratch') if artifact_dir else '<artifactDirectoryPath>/scratch/'}'. "
                "Delegate workspace modifications to persistent Mode C Swarm workers (workspace='share'), Mode B run_workflow, "
                "or invoke_subagent ('flash'/'flash_lite' for 80%+ routine work, 'gemini-4-neon-high'/'gemini-4-neon-medium' for @planner, "
                "'gemini-4-neon-high' for Tier-1 @councillor, 'gemini-4-carbon-high' for Tier-2 @councillor/critical audits)."
            ),
        }

    if tool_lower in READ_FILE_TOOLS:
        target_path = extract_target_path(args)
        if target_path and is_allowed_read_path(target_path, artifact_dir):
            return {"decision": "allow"}

        return {
            "decision": "deny",
            "reason": (
                f"[Orchestrator Pure-Dispatcher Guard] Main Session is restricted from reading workspace files directly ('{target_path or 'unknown'}'). "
                "The Main Session is a strictly Pure Dispatcher and may only read files inside its artifact directory "
                f"('{artifact_dir or '<artifactDirectoryPath>'}') or skill/plugin configurations. "
                "You MUST delegate all workspace exploration and file reading to a subagent via 'invoke_subagent' "
                "(Model='flash' or 'flash_lite') or Mode B 'run_workflow'."
            ),
        }

    return {
        "decision": "deny",
        "reason": (
            f"[Orchestrator Pure-Dispatcher Guard] Direct execution of '{tool_name}' in the Main Session is prohibited. "
            "The Main Session is a strictly Pure Dispatcher. Delegate reconnaissance, file operations, "
            "terminal commands, and MCP calls to Mode B 'run_workflow', Mode C Swarm workers (workspace='share'), or 'invoke_subagent' "
            "(Hydrogen 'flash'/'flash_lite' for 80%+ recon/routine work; 'gemini-4-neon-high' (multi-WP) / 'gemini-4-neon-medium' (single-WP) for @planner; "
            "'gemini-4-neon-high' for Tier-1 @councillor; 'gemini-4-carbon-high' for Tier-2 @councillor & critical audits; "
            "Main Session default runs on standalone 'gemini-4-neon-medium'), run Phase 0.5 Grill-Me ('ask_question'), "
            "and delegate planning to Neon @planner via swarm(action='add', name='planner', model='gemini-4-neon-high', fork='coordinator', brief='...')."
        ),
    }


def _log_fail_open(msg: str) -> None:
    try:
        sys.stderr.write(f"[Orchestrator Guard] fail-open: {msg}\n")
        sys.stderr.flush()
    except Exception:
        pass


def _is_complete_json_text(candidate: str) -> bool:
    if not candidate:
        return False
    if candidate[-1] not in ("}", "]", '"') and not (
        candidate in ("true", "false", "null") or candidate[-1].isdigit()
    ):
        return False
    try:
        json.loads(candidate)
        return True
    except (json.JSONDecodeError, ValueError):
        return False


def _read_stdin_nonblocking(
    timeout_sec: float = 2.0, max_bytes: int = MAX_STDIN_BYTES
) -> str:
    """
    Reads a JSON payload from sys.stdin without blocking indefinitely on stalled
    pipes or missing trailing newlines, bounded by `timeout_sec` and `max_bytes`.
    """
    stdin_obj = sys.stdin
    if stdin_obj is None:
        return ""

    limit = max(1, int(max_bytes))
    if isinstance(stdin_obj, io.StringIO):
        return stdin_obj.read(limit)

    timeout = max(0.05, float(timeout_sec))
    deadline = time.monotonic() + timeout

    fd: Optional[int] = None
    if os.name == "posix":
        try:
            cand_fd = stdin_obj.fileno()
            if isinstance(cand_fd, int) and cand_fd >= 0:
                fd = cand_fd
        except (AttributeError, ValueError, OSError, io.UnsupportedOperation):
            fd = None

    if fd is not None:
        raw_chunks: List[bytes] = []
        total_bytes = 0
        timed_out = False
        try:
            while total_bytes < limit:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    break
                try:
                    readable, _, _ = select.select([fd], [], [], remaining)
                except InterruptedError:
                    continue
                if not readable:
                    timed_out = True
                    break
                to_read = min(65536, limit - total_bytes)
                try:
                    chunk = os.read(fd, to_read)
                except (InterruptedError, BlockingIOError):
                    continue
                if not chunk:
                    break
                raw_chunks.append(chunk)
                total_bytes += len(chunk)

                try:
                    more_ready, _, _ = select.select([fd], [], [], 0.0)
                except (InterruptedError, ValueError, OSError):
                    more_ready = []
                if not more_ready:
                    decoded = b"".join(raw_chunks).decode("utf-8", errors="replace")
                    if _is_complete_json_text(decoded.strip()):
                        return decoded
        except (OSError, ValueError) as exc:
            _log_fail_open(f"stdin read error ({type(exc).__name__})")
            return ""

        decoded = b"".join(raw_chunks).decode("utf-8", errors="replace")
        if timed_out:
            if _is_complete_json_text(decoded.strip()):
                return decoded
            _log_fail_open(f"stdin read timed out after {timeout_sec:.2f}s")
            return ""
        return decoded

    # Fallback daemon-thread reader for non-fd streams / non-POSIX platforms
    chunks: List[str] = []
    done = threading.Event()
    read_error: List[BaseException] = []

    def _reader() -> None:
        try:
            chars_read = 0
            while chars_read < limit:
                if time.monotonic() >= deadline:
                    break
                max_chunk = min(65536, limit - chars_read)
                try:
                    line = stdin_obj.readline(max_chunk)
                except TypeError:
                    line = stdin_obj.readline()
                if line == "":
                    break
                chunks.append(line)
                chars_read += len(line)
                if chars_read >= limit:
                    break
                candidate = "".join(chunks).strip()
                if _is_complete_json_text(candidate):
                    break
        except BaseException as exc:
            read_error.append(exc)
        finally:
            done.set()

    thread = threading.Thread(target=_reader, name="stdin-reader", daemon=True)
    thread.start()

    remaining_wait = max(0.05, deadline - time.monotonic())
    if not done.wait(timeout=remaining_wait):
        _log_fail_open(f"stdin read timed out after {timeout_sec:.2f}s")
        return ""

    if read_error:
        _log_fail_open(f"stdin read error ({type(read_error[0]).__name__})")
        return ""

    return "".join(chunks)[:limit]


def _emit_json(obj: Dict[str, Any]) -> None:
    try:
        sys.stdout.write(json.dumps(obj, ensure_ascii=True))
        sys.stdout.flush()
    except (BrokenPipeError, OSError):
        pass


def _emit_allow() -> None:
    _emit_json({"decision": "allow"})


def main() -> None:
    try:
        if hasattr(sys.stdin, "reconfigure"):
            sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")

        raw_stdin = _read_stdin_nonblocking()
        if not raw_stdin or not raw_stdin.strip():
            _log_fail_open("empty stdin payload")
            _emit_allow()
            return

        try:
            payload = json.loads(raw_stdin)
        except Exception as exc:
            _log_fail_open(f"malformed JSON payload ({type(exc).__name__})")
            _emit_allow()
            return

        if not isinstance(payload, dict):
            _log_fail_open(
                f"expected JSON object payload, got {type(payload).__name__}"
            )
            _emit_allow()
            return

        result = evaluate_pre_tool_use(payload)
        _emit_json(result)
    except Exception as exc:
        _log_fail_open(f"guard evaluation error ({type(exc).__name__}: {exc})")
        _emit_allow()


if __name__ == "__main__":
    main()
