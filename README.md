# urirun-connector-agents

One `agent://` surface over every installed AI coding tool — Claude Code, Codex, opencode,
Aider, Ollama, Qoder, Cursor, Gemini. Detects what's installed and dispatches a task to any
of them through a uniform route. Because it's a urirun connector, the same declaration is
also an **MCP tool, an A2A skill, an OpenAPI operation, and a CLI** — so koru (and other
agents) delegate work over MCP/A2A to whichever coding tool is available.

| route | does |
|---|---|
| `agent://{node}/tools/query/list` | detect installed AI tools + which run headless |
| `agent://{node}/task/command/run` | run a task via `agent=auto` (best installed) or a named tool |

Part of the ifURI solution · Apache-2.0
