# contextbridge

Cross-IDE context handoff MCP server + CLI.

Current status: skeleton (Task 1). The actual CLI/MCP server is wired up in later tasks.

## Install (dev)

```bash
uv venv
uv pip install -e ".[dev]"
```

Or with `pip` + `venv`:

```bash
python -m venv .venv
. .venv/Scripts/activate   # Windows / Git Bash
pip install -e ".[dev]"
```

## Run

```bash
python -m contextbridge
```
