# One @conn.handler → every surface (URI/MCP/A2A/OpenAPI/CLI); agent dispatch is injectable.
from urirun_connector_agents import core


def test_all_surfaces_from_one_declaration():
    conn = core.conn
    assert list((conn.bindings().get("routes") or conn.bindings().get("bindings") or {}))
    assert conn.mcp_tools() and conn.a2a_card()["skills"]
    oa = conn.openapi()
    assert oa["openapi"].startswith("3.") and "/task/command/run" in oa["paths"]


def test_tools_list_detects_by_which(monkeypatch):
    monkeypatch.setattr(core, "_which", lambda n: "/usr/bin/" + n if n in ("claude", "aider", "qoder") else None)
    r = core.tools_list()
    assert set(r["available"]) == {"claude", "aider", "qoder"}
    assert r["headless"] == ["claude", "aider"] and r["preferred"] == "claude"   # qoder is gui
    assert r["available"]["qoder"]["headless"] is False


def test_task_run_auto_selects_and_invokes(monkeypatch):
    monkeypatch.setattr(core, "_which", lambda n: "/usr/bin/claude" if n == "claude" else None)
    seen = {}
    class CP: returncode=0; stdout="done"; stderr=""
    def fake_run(argv, **k): seen["argv"]=argv; return CP()
    monkeypatch.setattr(core.subprocess, "run", fake_run)
    r = core.task_run(prompt="write a hello", agent="auto")
    assert r["ok"] and r["agent"] == "claude" and seen["argv"] == ["claude", "-p", "write a hello"]


def test_task_run_no_agent_available(monkeypatch):
    monkeypatch.setattr(core, "_which", lambda n: None)
    r = core.task_run(prompt="x")
    assert r["ok"] is False and "no headless agent" in r["error"]


def test_named_gui_agent_rejected(monkeypatch):
    monkeypatch.setattr(core, "_which", lambda n: "/usr/bin/qoder" if n == "qoder" else None)
    r = core.task_run(prompt="x", agent="qoder")   # qoder is GUI → not dispatchable
    assert r["ok"] is False
