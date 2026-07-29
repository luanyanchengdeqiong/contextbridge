"""Entry point: `python -m contextbridge` and `cb`/`contextbridge` scripts.

- `cb serve`              → stdio MCP server(给本地 IDE 用,如 ZCode/Cursor)
- `cb serve --http`       → Streamable HTTP MCP server(给远程/网络测试用)
- `cb <subcommand>`       → run the Typer CLI(export/list/show/import/clear)
"""
import sys
from .cli import app


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        # 剥离 'serve' 后,剩下的交给一个专门的 Typer 子命令处理
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        _run_serve()
        return
    app()


def _run_serve() -> None:
    """解析 serve 子选项并启动对应 transport 的 MCP server。"""
    import typer

    serve_app = typer.Typer(add_completion=False)

    @serve_app.command()
    def _serve(
        http: bool = typer.Option(False, "--http", help="用 Streamable HTTP 传输(默认 stdio)"),
        host: str = typer.Option("127.0.0.1", "--host", "-H", help="HTTP 监听地址(远程测试用 0.0.0.0)"),
        port: int = typer.Option(8000, "--port", "-p", help="HTTP 监听端口"),
    ):
        """启动 MCP server。默认 stdio;--http 启动 Streamable HTTP。"""
        from .server import mcp
        if http:
            mcp.settings.host = host
            mcp.settings.port = port
            typer.echo(f"contextbridge MCP (streamable-http) on http://{host}:{port}/mcp")
            mcp.run(transport="streamable-http")
        else:
            mcp.run(transport="stdio")

    serve_app()


# [project.scripts] 入口期望可调用对象
app_cli = main


if __name__ == "__main__":
    main()
