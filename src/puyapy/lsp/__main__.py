import argparse
import sys

import attrs

from puya.log import LogLevel, configure_logging, get_logger
from puyapy.lsp import constants


@attrs.define(kw_only=True)
class PuyaPyLspOptions:
    stdio: bool = False
    host: str = "localhost"
    socket: int = 8888


def main() -> None:
    parser = argparse.ArgumentParser(
        prog=constants.NAME,
        description="puyapy language server, defaults to listening on localhost:8888",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s ({constants.VERSION})")
    parser.add_argument("--stdio", action="store_true", help="start a stdio server")
    parser.add_argument("--host", default="localhost", help="bind to this address")
    parser.add_argument("--socket", type=int, default=8888, help="bind to this port")

    namespace = parser.parse_args()
    options = PuyaPyLspOptions(**vars(namespace))

    # logging to stdout interferes with stdio protocol, so log to stderr instead
    log_file = sys.stderr if options.stdio else sys.stdout
    configure_logging(min_log_level=LogLevel.debug, file=log_file)
    _start_server(options)


def _start_server(options: PuyaPyLspOptions) -> None:
    # defer server import until logging is configured
    from puyapy.lsp.server import server

    logger = get_logger(__name__)

    if options.stdio:
        logger.info("starting stdio server")
        server.start_io()
    else:
        logger.info(f"starting tcp server at {options.host}:{options.socket}")
        server.start_tcp(options.host, options.socket)


if __name__ == "__main__":
    main()
