import sys

import cyclopts

from puya import log
from puyapy.lsp.log import configure_logging
from puyapy.lsp.server import create_server

app = cyclopts.App(help="puyapy langauge server", help_on_error=True)


@app.default
def main(
    *,
    stdio: bool = True,
    host: str = "localhost",
    port: int = 8888,
    log_level: log.LogLevel = log.LogLevel.info,
) -> None:
    """
    Starts the puyapy language server

    Parameters:
        stdio (bool): Use stdio
        host (str): Specifies the hostname
        port (int): Specifies the port number
        log_level: (LogLevel): Minimum log level to output
    """
    # logging to stdout interferes with stdio protocol, so log to stderr instead
    log_file = sys.stderr if stdio else sys.stdout
    configure_logging(min_log_level=log_level, file=log_file)
    server = create_server()
    if stdio:
        server.start_io()
    else:
        server.start_tcp(host, port)


if __name__ == "__main__":
    app()
