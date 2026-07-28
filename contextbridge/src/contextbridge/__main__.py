"""Entry point: `python -m contextbridge` and `cb`/`contextbridge` scripts.

- `cb serve` → start MCP stdio server (for Claude Code / Cursor integration)
- `cb <subcommand>` → run the Typer CLI
"""
import sys
from .cli import app


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        # 剥离 'serve' 参数后启动 MCP server
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        from .server import mcp
        mcp.run(transport="stdio")
        return
    app()


# [project.scripts] 入口期望可调用对象
app_cli = main


if __name__ == "__main__":
    main()
