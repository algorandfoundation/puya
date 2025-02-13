import asyncio
import shutil
import sys
import typing
import uuid
from collections import defaultdict
from collections.abc import AsyncIterator
from datetime import datetime
from typing import TextIO

import pytest
import pytest_asyncio
from cattrs import Converter
from lsprotocol import types as lsp
from pygls.lsp.client import LanguageClient
from pygls.lsp.server import LanguageServer
from pygls.protocol import LanguageServerProtocol, lsp_method

pytestmark = pytest.mark.asyncio(loop_scope="module")

_WORKSPACE_ROOT = "file:///fake-location"
_HELLO_WORLD_SRC = """
from algopy import ARC4Contract, String, arc4

class HelloWorldContract(ARC4Contract):
    @arc4.abimethod
    def hello(self, name: String) -> String:
        return "Hello, " + name
"""
_INT_ASSIGNMENT = "        i = 234"


async def test_open_doc_updates_diagnostics(
    unique_uri: str, harness: "_LanguageServerHarness"
) -> None:
    harness.open_doc(
        uri=unique_uri,
        text=_HELLO_WORLD_SRC,
    )
    notification1 = await harness.wait_for_diagnostic()

    assert notification1.uri == unique_uri
    assert notification1.version == 1
    assert notification1.diagnostics == []


async def test_doc_change_updates_diagnostics(
    unique_uri: str, harness: "_LanguageServerHarness"
) -> None:
    harness.open_doc(
        uri=unique_uri,
        text=_HELLO_WORLD_SRC,
    )
    # wait for expected diagnostics
    await harness.wait_for_diagnostic()

    harness.insert_lines(
        uri=unique_uri,
        lines={
            6: _INT_ASSIGNMENT,
        },
    )

    notification = await harness.wait_for_diagnostic()
    assert notification.uri == unique_uri
    assert notification.version == 2
    (diag,) = notification.diagnostics
    assert diag.message == "a Python literal is not valid at this location"
    assert diag.severity == lsp.DiagnosticSeverity.Error
    assert diag.source == "puyapy"
    assert diag.range == lsp.Range(
        start=lsp.Position(line=6, character=12), end=lsp.Position(line=6, character=15)
    )


async def test_code_fix_suggested(unique_uri: str, harness: "_LanguageServerHarness") -> None:
    contract_with_int_assignment = _HELLO_WORLD_SRC.splitlines()
    contract_with_int_assignment[6:6] = [_INT_ASSIGNMENT]
    harness.open_doc(
        uri=unique_uri,
        text="\n".join(contract_with_int_assignment),
    )
    # wait for expected diagnostics
    diagnostics = await harness.wait_for_diagnostic()
    assert diagnostics.uri == unique_uri

    code_actions = await harness.client.text_document_code_action_async(
        lsp.CodeActionParams(
            text_document=lsp.TextDocumentIdentifier(
                uri=unique_uri,
            ),
            range=lsp.Range(
                start=lsp.Position(line=0, character=0),
                end=lsp.Position(line=len(contract_with_int_assignment), character=0),
            ),
            context=lsp.CodeActionContext(
                diagnostics=diagnostics.diagnostics,
            ),
        )
    )
    assert code_actions is not None, "expected response"
    assert len(code_actions) == 1
    (code_action,) = code_actions
    assert isinstance(code_action, lsp.CodeAction)
    assert code_action.title == "Use algopy.UInt64"
    assert code_action.kind == "quickfix"
    assert code_action.edit is not None
    assert code_action.edit.changes is not None
    assert unique_uri in code_action.edit.changes
    assert code_action.edit.changes[unique_uri][0].new_text == "UInt64(234)"


async def test_dependencies_diagnostics_update(harness: "_LanguageServerHarness") -> None:
    doc_a = f"{_WORKSPACE_ROOT}/a.py"
    doc_b = f"{_WORKSPACE_ROOT}/b.py"
    harness.open_doc(
        uri=doc_a,
        text="""
from algopy import UInt64

def five() -> UInt64:
    return UInt64(5)
""",
    )
    harness.open_doc(
        uri=doc_b,
        text="""
from algopy import ARC4Contract, UInt64, arc4
from a import five

class Contract(ARC4Contract):

    @arc4.abimethod
    def high(self) -> UInt64:
        return five()
""",
    )

    diag1 = await harness.wait_for_diagnostic()
    diag2 = await harness.wait_for_diagnostic()

    # can't assume an order...
    if diag1.uri == doc_a:
        diag_a = diag1
        diag_b = diag2
    else:
        diag_a = diag2
        diag_b = diag1

    assert diag_a.uri == doc_a
    assert (
        diag_a.diagnostics[0].message == "free functions must be annotated with @algopy.subroutine"
    )

    assert diag_b.uri == doc_b
    assert (
        diag_b.diagnostics[0].message
        == "Cannot invoke a.five as it is not decorated with algopy.subroutine"
    )

    harness.insert_lines(
        uri=doc_a,
        lines={
            (1, 25): ", subroutine",
            3: "@subroutine",
        },
    )

    diag1 = await harness.wait_for_diagnostic()
    diag2 = await harness.wait_for_diagnostic()

    if diag1.uri == doc_a:
        diag_a = diag1
        diag_b = diag2
    else:
        diag_a = diag2
        diag_b = diag1

    assert diag_a.uri == doc_a
    assert diag_a.version == harness.current_version(doc_a)
    assert diag_a.diagnostics == []

    assert diag_b.uri == doc_b
    assert diag_b.version == harness.current_version(doc_b)
    assert diag_b.diagnostics == []


# TODO: add test case for more complex dependencies including relative imports
#       and reexporting algopy


async def test_backend_error(harness: "_LanguageServerHarness", unique_uri: str) -> None:
    harness.open_doc(
        uri=unique_uri,
        text="""
from algopy import UInt64, arc4

class ContractA(arc4.ARC4Contract):

    @arc4.abimethod
    def call(self) -> None:
        arc4.abi_call("some_method(string)void", UInt64(1234), app_id=1234)
""",
    )
    notification = await harness.wait_for_diagnostic()

    assert notification.uri == unique_uri
    assert notification.version == 1
    assert len(notification.diagnostics) == 1
    (diag,) = notification.diagnostics
    assert diag.message == "cannot encode algopy.UInt64 to algopy.arc4.String"


async def test_non_puyapy_code_is_ignored(
    harness: "_LanguageServerHarness", unique_uri: str
) -> None:
    harness.open_doc(
        uri=unique_uri,
        text="""
import sys

print(sys.argv)
""",
    )
    with pytest.raises(TimeoutError):
        await harness.wait_for_diagnostic()


@pytest.fixture
def unique_uri() -> str:
    name = str(uuid.uuid4()).replace("-", "")
    return _WORKSPACE_ROOT + f"/{name}.py"


@pytest_asyncio.fixture(loop_scope="module", scope="module")
async def harness(client: "_LanguageClient") -> AsyncIterator["_LanguageServerHarness"]:
    harness = _LanguageServerHarness(client)
    await harness.initialize()
    yield harness


@pytest_asyncio.fixture(loop_scope="module", scope="module")
async def client() -> "_LanguageClient":
    # Find the puya executable path
    puya_path = shutil.which("puyapy-ls")
    assert puya_path is not None, "could not find puyapy-ls executable"
    client = _LanguageClient("puyapy-ls", "99", _LanguageServerProtocol)
    # start the server
    await client.start_io(puya_path)
    return client


class _LanguageServerHarness:
    """Abstracts common LSP interactions between client and server"""

    def __init__(self, client: LanguageClient) -> None:
        self.client = client
        self.protocol = typing.cast(_LanguageServerProtocol, client.protocol)
        self._uri_versions = defaultdict[str, int](int)

    def _next_version(self, uri: str) -> int:
        self._uri_versions[uri] += 1
        return self._uri_versions[uri]

    def current_version(self, uri: str) -> int:
        return self._uri_versions[uri]

    async def initialize(self) -> None:
        venv = sys.prefix
        initialized = await self.client.initialize_async(
            lsp.InitializeParams(
                capabilities=lsp.ClientCapabilities(
                    text_document=lsp.TextDocumentClientCapabilities(
                        publish_diagnostics=lsp.PublishDiagnosticsClientCapabilities(
                            version_support=True, related_information=True
                        ),
                        synchronization=lsp.TextDocumentSyncClientCapabilities(
                            dynamic_registration=True,
                            did_save=True,
                        ),
                    )
                ),
                initialization_options={"analysisPrefix": venv},
                workspace_folders=[
                    lsp.WorkspaceFolder(
                        uri=_WORKSPACE_ROOT,
                        name="algorand-python",
                    )
                ],
            )
        )
        assert initialized.server_info
        assert initialized.server_info.name == "puyapy"

    def open_doc(self, uri: str, text: str) -> None:
        self.client.text_document_did_open(
            lsp.DidOpenTextDocumentParams(
                text_document=lsp.TextDocumentItem(
                    uri=uri,
                    language_id="algopy",
                    version=self._next_version(uri),
                    text=text,
                )
            )
        )

    async def wait_for_diagnostic(self) -> lsp.PublishDiagnosticsParams:
        return await self.protocol.wait_for_notification(lsp.PublishDiagnosticsParams)

    def insert_lines(self, uri: str, lines: dict[int | tuple[int, int], str]) -> None:
        self.client.text_document_did_change(
            lsp.DidChangeTextDocumentParams(
                text_document=lsp.VersionedTextDocumentIdentifier(
                    uri=uri,
                    version=self._next_version(uri),
                ),
                content_changes=[
                    lsp.TextDocumentContentChangePartial(
                        _insert_range(line),
                        text=text + "\n",
                    )
                    for line, text in lines.items()
                ],
            )
        )


def _insert_range(range_: int | tuple[int, int]) -> lsp.Range:
    if isinstance(range_, tuple):
        line, character = range_
    else:
        line = range_
        character = 0
    position = lsp.Position(line=line, character=character)
    return lsp.Range(
        start=position,
        end=position,
    )


class _LanguageServerProtocol(LanguageServerProtocol):
    """Captures notifications to be consumed by tests"""

    def __init__(self, server: LanguageServer, converter: Converter) -> None:
        super().__init__(server, converter)
        self._notifications = list[object]()
        self._notification_event: asyncio.Event | None = None

    def _handle_notification(self, method_name: str, params: typing.Any) -> None:  # noqa: ANN401
        super()._handle_notification(method_name, params)
        self._notifications.append(params)
        if self._notification_event:
            self._notification_event.set()

    async def wait_for_notification[T](self, typ: type[T]) -> T:
        assert not self._notification_event, "cannot wait for multiple notifications"

        self._notification_event = asyncio.Event()
        try:
            await asyncio.wait_for(self._notification_event.wait(), timeout=3)
        except TimeoutError:
            raise TimeoutError("timed out waiting for notification") from None
        finally:
            self._notification_event = None
        result = self._notifications[-1]
        assert isinstance(result, typ), f"expected notification of type {typ.__name__}"
        return result

    @lsp_method(lsp.WINDOW_SHOW_MESSAGE)
    def show_message(self, params: lsp.ShowMessageParams) -> None:
        _client_output(f"{params.type}: {params.message}")


class _LanguageClient(LanguageClient):
    """Override LanguageClient so stderr of service can be forwarded to stdout of test"""

    @typing.override
    async def start_io(self, cmd: str, *args: object, **kwargs: object) -> None:
        await super().start_io(cmd, *args, **kwargs)

        # forward stderr of server process to stdout for visibility when testing
        assert self._server is not None, "expected server to be running"
        stderr = self._server.stderr
        assert stderr is not None, "expected stderr to be defined"
        task = asyncio.create_task(_read_stderr(stderr))

        # ensure task reading stderr is cleaned up
        self._async_tasks.append(task)


async def _read_stderr(stderr: asyncio.StreamReader) -> None:
    while True:
        try:
            line = await asyncio.wait_for(stderr.readline(), timeout=0.1)
        except TimeoutError:
            continue
        if not line:
            break
        _server_output(line.decode("utf8").strip(), file=sys.stdout)


def _server_output(msg: str, *, file: TextIO | None = None) -> None:
    _output(f"server: {msg}", file=file)


def _client_output(msg: str, *, file: TextIO | None = None) -> None:
    _output(f"client: {msg}", file=file)


def _output(msg: str, *, file: TextIO | None) -> None:
    time_str = datetime.now(tz=None).strftime("%H:%M:%S.%f").rstrip("0")  # noqa: DTZ005
    print(f"[{time_str}] {msg}", file=file or sys.stdout, flush=True)
