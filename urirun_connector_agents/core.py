# Author: Tom Sapletta · Part of the ifURI solution.
"""urirun-connector-agents — one agent:// surface over every installed AI coding tool.

Claude Code, Codex, opencode, Aider, Ollama, Qoder, Cursor … each has its own CLI. This
connector detects which are installed and dispatches a task to any of them through a
uniform ``agent://host/task/command/run``. Because it is a urirun connector, it is
automatically exposed as an MCP tool and an A2A card — so koru (and other agents) can
delegate work to whichever coding tool is available, over MCP/A2A, without knowing each
tool's flags. This is how koru joins the MCP + A2A ecosystem and drives real work.

Built to URI_NATIVE_CONNECTOR_CHECKLIST: lazy imports, handlers never raise (envelope),
detection is a cheap query; task-run is isolated (spawns a real coding tool).
"""
from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any

import urirun

CONNECTOR_ID = "agents"
conn = urirun.connector(CONNECTOR_ID, scheme="agent")


# id → adapter. ``argv`` builds the headless command for a prompt; ``gui`` tools have no
# headless task mode (listed as present but not auto-dispatchable).
_ADAPTERS: dict[str, dict[str, Any]] = {
    "claude":   {"bin": "claude",   "argv": lambda p, m: ["claude", "-p", p], "gui": False, "desc": "Claude Code (print mode)"},
    "codex":    {"bin": "codex",    "argv": lambda p, m: ["codex", "exec", p], "gui": False, "desc": "OpenAI Codex CLI (exec)"},
    "opencode": {"bin": "opencode", "argv": lambda p, m: ["opencode", "run", p], "gui": False, "desc": "opencode (run)"},
    "aider":    {"bin": "aider",    "argv": lambda p, m: (["aider", "--message", p, "--yes-always", "--no-auto-commits"]
                                                          + (["--model", m] if m else [])),
                 "gui": False, "desc": "Aider (OpenRouter via --model)"},
    "ollama":   {"bin": "ollama",   "argv": lambda p, m: ["ollama", "run", m or "llama3", p], "gui": False, "desc": "Ollama (local model)"},
    "qoder":    {"bin": "qoder",    "argv": None, "gui": True, "desc": "Qoder IDE (GUI)"},
    "cursor":   {"bin": "cursor",   "argv": None, "gui": True, "desc": "Cursor IDE (GUI)"},
    "gemini":   {"bin": "gemini",   "argv": lambda p, m: ["gemini", "-p", p], "gui": False, "desc": "Gemini CLI"},
}
# preference order for auto-selection (headless, OpenRouter-friendly first)
_PREF = ("aider", "claude", "codex", "opencode", "gemini", "ollama")


def _ok(**kw: Any) -> dict[str, Any]:
    return urirun.ok(connector=CONNECTOR_ID, **kw)


def _fail(msg: str, action: str, **extra: Any) -> dict[str, Any]:
    extra.pop("error", None)
    return urirun.fail(msg, connector=CONNECTOR_ID, action=action, **extra)


def _which(name: str) -> str | None:
    return shutil.which(name)


def _available() -> dict[str, dict]:
    out = {}
    for aid, a in _ADAPTERS.items():
        path = _which(a["bin"])
        if path:
            out[aid] = {"path": path, "gui": a["gui"], "headless": not a["gui"], "desc": a["desc"]}
    return out


@conn.handler("tools/query/list", isolated=False,
              meta={"label": "List installed AI coding tools (Claude Code, Codex, opencode, Aider, Ollama, …)"})
def tools_list() -> dict[str, Any]:
    """Detect which AI coding tools are installed and which can run a task headless.
    The catalog koru/an A2A peer reads before delegating."""
    avail = _available()
    headless = [a for a in _PREF if a in avail and avail[a]["headless"]]
    return _ok(action="agents-list", available=avail, headless=headless,
               preferred=(headless[0] if headless else None))


@conn.handler("executors/query/list", isolated=False,
              meta={"label": "IFURI-200: wykonawcy headless dostępni jako fallback (agent:// executor chain)"})
def executors_query_list() -> dict[str, Any]:
    avail = _available()
    headless = [a for a in _PREF if a in avail and avail[a]["headless"]]
    return _ok(action="executors-list", executors=headless, count=len(headless),
               fallback_ready=bool(headless), preferred=(headless[0] if headless else None))


@conn.handler("executor/query/health", isolated=False,
              meta={"label": "IFURI-200: zdrowie wykonawcy — czy agent:// może wykonać fallback"})
def executor_query_health(agent: str = "") -> dict[str, Any]:
    avail = _available()
    headless = [a for a in _PREF if a in avail and avail[a]["headless"]]
    if agent:
        ok = agent in avail and avail[agent]["headless"]
        return _ok(action="executor-health", agent=agent, healthy=ok,
                   reason="dostępny headless" if ok else "brak/gui-only")
    return _ok(action="executor-health", healthy=bool(headless), executors=headless,
               reason="fallback gotowy" if headless else "BRAK wykonawcy → eskalacja human")


@conn.handler("task/command/run", isolated=True,
              meta={"label": "Run a coding task via an AI tool (agent=auto picks the best installed headless one)"})
def task_run(prompt: str = "", agent: str = "auto", cwd: str = "", model: str = "",
             timeout: float = 600.0) -> dict[str, Any]:
    """Dispatch a task to a coding tool. ``agent=auto`` picks the first installed headless
    tool by preference; or name one (claude|codex|opencode|aider|ollama|gemini). Returns
    the tool's output. This is the seam koru uses to execute a ticket via any agent."""
    if not prompt:
        return _fail("prompt is required", "agents-run")
    avail = _available()
    chosen = _select(agent, avail)
    if not chosen:
        return _fail(f"no headless agent available (agent={agent!r}); installed: {list(avail)}",
                     "agents-run", available=list(avail))
    adapter = _ADAPTERS[chosen]
    argv = adapter["argv"](prompt, model)
    try:
        cp = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,  # noqa: S603
                            cwd=cwd or None)
    except Exception as exc:  # noqa: BLE001
        return _fail(str(exc), "agents-run", agent=chosen)
    return _ok(action="agents-run", agent=chosen, returncode=cp.returncode,
               ok_run=cp.returncode == 0, stdout=(cp.stdout or "")[-4000:],
               stderr=(cp.stderr or "")[-1000:])


def _select(agent: str, avail: dict) -> str | None:
    if agent and agent != "auto":
        a = _ADAPTERS.get(agent)
        return agent if (agent in avail and a and not a["gui"]) else None
    for aid in _PREF:
        if aid in avail and not _ADAPTERS[aid]["gui"]:
            return aid
    return None


def urirun_bindings() -> dict[str, Any]:
    return conn.bindings()


def connector_manifest() -> dict[str, Any]:
    m = urirun.load_manifest(__package__) or {"id": CONNECTOR_ID}
    try:
        from urirun_connectors_toolkit.connector_sdk import manifest_routes
        m["routes"] = manifest_routes(urirun_bindings())
    except Exception:  # noqa: BLE001
        pass
    return m


def main(argv: list[str] | None = None) -> int:
    return conn.cli(argv, manifest_prose=urirun.load_manifest(__package__))


if __name__ == "__main__":
    raise SystemExit(main())
