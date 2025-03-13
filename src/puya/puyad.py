import argparse
import contextlib
import sys
import typing
from importlib.metadata import version
from pathlib import Path

import attrs
from pygls.protocol.json_rpc import JsonRPCProtocol
from pygls.server import JsonRPCServer

from puya.awst.nodes import AWST
from puya.awst.serialize import get_converter
from puya.compile import awst_to_teal
from puya.errors import PuyaExitError, log_exceptions
from puya.log import Log, LogLevel, configure_logging, logging_context
from puya.options import PuyaOptions
from puya.parse import DictSourceProvider

NAME = "puyad"
VERSION = version("puyapy")


@attrs.frozen
class AnalyseParams:
    awst: AWST
    compilation_set: dict[str, Path]


@attrs.frozen
class AnalyseResult:
    logs: list[Log]


@attrs.frozen(kw_only=True)
class _RPCMessage:
    id: int | str
    jsonrpc: str = attrs.field(default="2.0")


@attrs.frozen(kw_only=True)
class AnalyseRequest(_RPCMessage):
    params: AnalyseParams
    method: typing.Literal["analyse"] = "analyse"


@attrs.frozen(kw_only=True)
class AnalyseResponse(_RPCMessage):
    result: AnalyseResult


# this is effectively what the lspprotcol does, good enough for now
_TYPES = {
    "analyse": (AnalyseRequest, AnalyseResponse),
}


class PuyaProtocol(JsonRPCProtocol):
    def get_message_type(self, method: str) -> type | None:
        return _TYPES.get(method, (None, None))[0]

    def get_result_type(self, method: str) -> type | None:
        return _TYPES.get(method, (None, None))[1]


server = JsonRPCServer(PuyaProtocol, get_converter)


@server.feature("analyse")
def analyse(params: AnalyseParams) -> AnalyseResult:
    options = PuyaOptions(optimization_level=0)
    with logging_context() as log_ctx, contextlib.suppress(PuyaExitError), log_exceptions():
        awst_to_teal(
            log_ctx,
            options,
            params.compilation_set,  # type: ignore[arg-type]
            DictSourceProvider({}),
            params.awst,
        )
    return AnalyseResult(logs=log_ctx.logs)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog=NAME,
        description=NAME,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s ({VERSION})")
    _namespace = parser.parse_args()

    # logging to stdout interferes with stdio protocol, so log to stderr instead
    log_file = sys.stderr
    configure_logging(min_log_level=LogLevel.info, file=log_file)
    server.start_io()


if __name__ == "__main__":
    main()
