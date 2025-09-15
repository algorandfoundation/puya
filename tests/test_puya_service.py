import asyncio
import gzip
import shutil
import sys
import typing
from collections.abc import AsyncGenerator
from contextvars import ContextVar
from pathlib import Path
from typing import TextIO

import attrs
import pytest
import pytest_asyncio
from lsprotocol.types import ResponseError
from pygls.client import JsonRPCClient
from pygls.exceptions import JsonRpcException, PyglsError
from pygls.protocol.json_rpc import RPCError

from puya.awst import nodes as awst_nodes
from puya.awst.serialize import awst_from_json, get_converter
from puya.main import PuyaOptionsWithCompilationSet
from puya.service import AnalyseParams, AnalyseResult, CompileParams, CompileResult, PuyaProtocol
from tests import EXAMPLES_DIR, VCS_ROOT
from tests.utils import get_awst_cache, log_to_str

pytestmark = pytest.mark.asyncio(loop_scope="module")


_ANALYSE_DIR = VCS_ROOT / "tests" / "analyse"
_HELLO_WORLD_PATH = EXAMPLES_DIR / "hello_world_arc4"
_EXPECTED_ANALYSE_OUTPUT = {
    _HELLO_WORLD_PATH: [],
    _ANALYSE_DIR / "reti.awst.json.zip": [
        "warning: Variable tokenPayoutRatio potentially used before assignment",
    ],
    _ANALYSE_DIR / "valid_awst_with_error": [
        "contract.py:7:38 error: cannot encode algopy.Bytes"
        " to algopy.arc4.UIntN[typing.Literal[64]]",
    ],
}


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "test_case_path" in metafunc.fixturenames:
        test_data = [
            (path, _create_analyse_params(path), expected_output)
            for path, expected_output in _EXPECTED_ANALYSE_OUTPUT.items()
        ]
        metafunc.parametrize(
            "test_case_path,params,expected_output", test_data, ids=[t[0].name for t in test_data]
        )


async def test_analyse(
    client: JsonRPCClient,
    test_case_path: Path,
    params: Path,
    expected_output: list[str],
) -> None:
    response = await client.protocol.send_request_async("analyse", params)
    assert isinstance(response, AnalyseResult)

    logs = [log_to_str(log, test_case_path) for log in response.logs]

    assert logs == expected_output, "analyse output different than expected"


async def test_compile_hello_world(client: JsonRPCClient, tmp_path: Path) -> None:
    path = _HELLO_WORLD_PATH
    awst = _create_analyse_params(path).awst
    compile_params = CompileParams(
        awst=awst,
        options=PuyaOptionsWithCompilationSet(
            compilation_set={
                node.id: tmp_path for node in awst if isinstance(node, awst_nodes.Contract)
            },
            output_teal=True,
        ),
        base_path=path,
    )

    response = await client.protocol.send_request_async("compile", compile_params)
    assert isinstance(response, CompileResult)

    approval_path = tmp_path / "HelloWorldContract.approval.teal"
    clear_path = tmp_path / "HelloWorldContract.clear.teal"
    assert approval_path.exists(), "expected approval to exist"
    assert clear_path.exists(), "expected clear to exist"

    logs = [log_to_str(log, path) for log in response.logs]
    assert logs == [
        f"info: Writing {approval_path.as_posix()}",
        f"info: Writing {clear_path.as_posix()}",
    ], "compile contained errors"


@pytest_asyncio.fixture(loop_scope="module", scope="module")
async def client() -> AsyncGenerator[JsonRPCClient]:
    client = await _start_client("serve", "--log-level=info")
    try:
        # yield client for test to use
        yield client
    finally:
        # shutdown and clean up the client
        client.protocol.send_request("shutdown")
        await client.stop()  # type: ignore[no-untyped-call]
        assert client.stopped, "expected client to have stopped"


_current_msg_id = ContextVar[str | int | None]("_current_msg_id", default=None)


class _PuyaProtocol(PuyaProtocol):
    # capture id if present in payload, so can fail requests if structuring fails
    # useful during development
    def structure_message(self, data: dict[str, typing.Any]) -> object:
        _current_msg_id.set(data.get("id"))
        return super().structure_message(data)


class _PuyaRPCClient(JsonRPCClient):
    @typing.override
    async def start_io(self, cmd: str, *args: object, **kwargs: object) -> None:
        await super().start_io(cmd, *args, **kwargs)

        # forward stderr of server process to stdout for visibility when testing
        stderr = self.server.stderr
        assert stderr is not None, "expected stderr to be defined"
        task = asyncio.create_task(_read_stderr(stderr))

        # ensure task reading stderr is cleaned up
        self._async_tasks.append(task)

    @property
    def server(self) -> asyncio.subprocess.Process:
        assert self._server is not None
        return self._server

    @typing.override
    def report_server_error(
        self, error: Exception, source: type[PyglsError] | type[JsonRpcException]
    ) -> None:
        # an error during a response would leave a test waiting
        # so respond with an error
        msg_id = _current_msg_id.get()
        if msg_id is not None:
            self.protocol.handle_message(
                _RPCError(
                    id=msg_id,
                    error=ResponseError(
                        code=0,
                        message=f"client error processing response: {error}",
                        data=None,
                    ),
                )
            )


@attrs.frozen
class _RPCError(RPCError):
    id: str | int
    error: ResponseError
    jsonrpc: str = "2.0"


def _server_output(msg: str, *, file: TextIO) -> None:
    print(f"server: {msg}", file=file, flush=True)


async def _read_stderr(stderr: asyncio.StreamReader) -> None:
    while True:
        try:
            line = await asyncio.wait_for(stderr.readline(), timeout=0.1)
        except TimeoutError:
            continue
        if not line:
            break
        _server_output(line.decode("utf8").strip(), file=sys.stdout)


async def _start_client(*args: str) -> _PuyaRPCClient:
    # Find the puya executable path
    puya_path = shutil.which("puya")
    assert puya_path is not None, "could not find puya executable"
    client = _PuyaRPCClient(_PuyaProtocol, get_converter)
    # start the server
    await client.start_io(puya_path, *args)
    return client


def _create_analyse_params(path: Path) -> AnalyseParams:
    if path.is_dir():
        cache = get_awst_cache(path)
        awst = cache.module_awst
    else:
        assert path.suffix == ".zip", "expected dir or zip"
        json_str = gzip.decompress(path.read_bytes()).decode("utf-8")
        awst = awst_from_json(json_str)

    return AnalyseParams(awst=awst)
