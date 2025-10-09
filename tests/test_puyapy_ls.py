import asyncio
import contextlib
import os
import platform
import shutil
import sys
import typing
import uuid
from collections import defaultdict
from collections.abc import AsyncIterator, Sequence
from datetime import datetime
from pathlib import Path
from typing import TextIO

import pytest
import pytest_asyncio
from cattrs import Converter
from lsprotocol import types as lsp
from pygls.lsp.client import LanguageClient
from pygls.lsp.server import LanguageServer
from pygls.protocol import LanguageServerProtocol, lsp_method

from puyapy.lsp.analyse import _uri_to_path

pytestmark = pytest.mark.asyncio(loop_scope="module")

_HELLO_WORLD_SRC = """
from algopy import ARC4Contract, String, arc4

class HelloWorldContract(ARC4Contract):
    @arc4.abimethod
    def hello(self, name: String) -> String:
        return "Hello, " + name
"""
_INT_ASSIGNMENT = "        i = 234"

# Timeout needs to cover analysis time and CPU contention.
# When running multiple tests in parallel, a simple hello world contract takes at least
# 1 second on an Apple M4 Pro due to mypy overheads
_DIAGNOSTIC_TIMEOUT = 10


async def test_open_doc_updates_diagnostics(
    unique_uri: str, harness: "_LanguageServerHarness"
) -> None:
    harness.open_doc(
        uri=unique_uri,
        text=_HELLO_WORLD_SRC,
    )
    diag_params = await harness.wait_for_diagnostic(unique_uri, 1)

    assert diag_params.diagnostics == []


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows only test")
async def test_open_doc_encoded_uri_updates_diagnostics(
    unique_uri: str, harness: "_LanguageServerHarness"
) -> None:
    # on windows + vscode uris may contain uri encoded values
    # e.g. for the colon in a drive name, this test ensures they are handled correctly
    assert unique_uri.startswith("file:///")
    file, drive, remaining = unique_uri.split(":", maxsplit=2)
    unique_uri = f"{file}:{drive}%3A{remaining}"

    harness.open_doc(
        uri=unique_uri,
        text=_HELLO_WORLD_SRC,
    )
    diag_params = await harness.wait_for_diagnostic(unique_uri, 1)

    assert diag_params.diagnostics == []


async def test_doc_change_updates_diagnostics(
    unique_uri: str, harness: "_LanguageServerHarness"
) -> None:
    harness.open_doc(
        uri=unique_uri,
        text=_HELLO_WORLD_SRC,
    )
    # wait for expected diagnostics
    await harness.wait_for_diagnostic(unique_uri, 1)

    harness.insert_lines(
        uri=unique_uri,
        lines={
            6: _INT_ASSIGNMENT,
        },
    )

    diag_params = await harness.wait_for_diagnostic(unique_uri, 2)
    assert len(diag_params.diagnostics) == 1, "expected 1 diagnostic"
    (diag,) = diag_params.diagnostics
    assert diag.message == "a Python literal is not valid at this location"
    assert diag.severity == lsp.DiagnosticSeverity.Error
    assert diag.source == "puyapy"
    assert diag.range == lsp.Range(
        start=lsp.Position(line=6, character=12), end=lsp.Position(line=6, character=15)
    )


async def test_code_fixes_suggested(unique_uri: str, harness: "_LanguageServerHarness") -> None:
    contract_requiring_fixes = """
from algopy import ARC4Contract, Array
from algopy.arc4 import abimethod

class HelloWorldContract(ARC4Contract):
    @abimethod
    def literal_fix(self) -> None:
        i = 123

    @abimethod
    def range_fix(self) -> None:
        for j in range(3):
            pass

    @abimethod
    def copy_needed(self) -> None:
        arr = Array[bool]()
        arr2 = arr

    def no_contract_dec(self) -> None:
        pass

def no_sub_dec() -> None:
    pass
"""
    harness.open_doc(
        uri=unique_uri,
        text=contract_requiring_fixes,
    )
    # wait for expected diagnostics
    diagnostics = await harness.wait_for_diagnostic(unique_uri, 1)
    assert len(diagnostics.diagnostics) == 5

    # now request code actions
    code_actions = await harness.code_actions(unique_uri)
    assert code_actions is not None, "expected response"
    assert [ca.title for ca in code_actions] == [
        "Use @algopy.subroutine",
        "Use @algopy.arc4.abimethod",
        "Use @algopy.arc4.baremethod",
        "Use @algopy.subroutine",
        "Use algopy.UInt64",
        "Use algopy.urange",
        "Add .copy()",
    ]
    meth_sub_action, _, _, _, uint64_action, urange_action, copy_action = code_actions
    assert isinstance(uint64_action, lsp.CodeAction)
    assert uint64_action.kind == "quickfix"
    edits = _get_edits(uint64_action, unique_uri)
    assert edits is not None
    assert [e.new_text for e in edits] == [
        "from algopy import UInt64\n",
        ")",
        "UInt64(",
    ]
    assert isinstance(meth_sub_action, lsp.CodeAction)
    edits = _get_edits(meth_sub_action, unique_uri)
    assert edits is not None
    assert [e.new_text for e in edits] == [
        "from algopy import subroutine\n",
        "\n    @subroutine",
    ]
    assert isinstance(urange_action, lsp.CodeAction)
    edits = _get_edits(urange_action, unique_uri)
    assert edits is not None
    assert [e.new_text for e in edits] == [
        "from algopy import urange\n",
        "urange",
    ]
    assert isinstance(copy_action, lsp.CodeAction)
    edits = _get_edits(copy_action, unique_uri)
    assert edits is not None
    assert [e.new_text for e in edits] == [".copy()"]


def _get_edits(action: lsp.CodeAction, uri: str) -> Sequence[lsp.TextEdit] | None:
    if action.edit is None or action.edit.changes is None:
        return None
    return action.edit.changes.get(uri)


def _first_line(arg: str | None) -> str | None:
    if arg is None:
        return arg
    return arg.strip().splitlines()[0]


@pytest.mark.parametrize(
    ("contract_header", "expected_import", "expected_symbol"),
    [
        (
            """
from algopy import arc4

class Contract(arc4.ARC4Contract):
    @arc4.abimethod
""",
            "from algopy import UInt64",
            "UInt64",
        ),
        (
            """
from algopy import *

class MyContract(arc4.ARC4Contract):
    @arc4.abimethod
""",
            None,
            "UInt64",
        ),
        (
            """
from algopy import arc4, UInt64 as alias

class Contract(arc4.ARC4Contract):
    @arc4.abimethod
""",
            None,
            "alias",
        ),
        (
            """
import algopy

class Contract(algopy.ARC4Contract):
    @algopy.arc4.abimethod
""",
            None,
            "algopy.UInt64",
        ),
        (
            """
import algopy as alias

class Contract(alias.ARC4Contract):
    @alias.arc4.abimethod
""",
            None,
            "alias.UInt64",
        ),
    ],
    ids=_first_line,
)
async def test_code_fix_symbol_aliases(
    unique_uri: str,
    harness: "_LanguageServerHarness",
    contract_header: str,
    expected_import: str | None,
    expected_symbol: str,
) -> None:
    harness.open_doc(
        uri=unique_uri,
        text=f"""{contract_header}
    def test(self) -> None:
        i = 123
""",
    )
    # wait for expected diagnostics
    diagnostics = await harness.wait_for_diagnostic(unique_uri, 1)
    assert [d.message for d in diagnostics.diagnostics] == [
        "a Python literal is not valid at this location"
    ]

    code_actions = await harness.code_actions(unique_uri)
    assert code_actions is not None, "expected response"
    assert len(code_actions) == 1, "expected 1 code action"
    (code_action,) = code_actions
    assert isinstance(code_action, lsp.CodeAction)
    assert code_action.title == "Use algopy.UInt64"
    assert code_action.edit is not None
    assert code_action.edit.changes is not None
    assert unique_uri in code_action.edit.changes

    # assert fix contains expected edits
    expected_edits = [")", f"{expected_symbol}("]
    if expected_import:
        expected_edits.insert(0, expected_import + "\n")
    actual_edits = [e.new_text for e in code_action.edit.changes[unique_uri]]
    assert actual_edits == expected_edits
    if expected_import:
        assert (
            code_action.edit.changes[unique_uri][0].range.start.line == 1
        ), "expected import statement to be on line 1"


@pytest.mark.parametrize(
    ("package", "import_method"),
    [
        ("package", "relative"),
        ("package", "absolute"),
        (None, "absolute"),
        # relative imports without a package are not supported
    ],
)
async def test_dependencies_diagnostics_update(
    workspace_root: Path,
    harness: "_LanguageServerHarness",
    *,
    package: str | None,
    import_method: typing.Literal["relative", "absolute"],
) -> None:
    package_name = f"{package}_{import_method}"
    working_dir = workspace_root / package_name
    working_dir.mkdir()
    if package:
        doc_init = (working_dir / "__init__.py").as_uri()
        harness.open_doc(uri=doc_init, text="\n")
    a_full_name = f"{package_name}.a" if package else "a"
    if import_method == "relative":
        a_import_name = ".a"
    else:
        a_import_name = a_full_name

    doc_a = (working_dir / "a.py").as_uri()
    doc_b = (working_dir / "b.py").as_uri()
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
        text=f"""
from algopy import ARC4Contract, UInt64, arc4
from {a_import_name} import five

class Contract(ARC4Contract):

    @arc4.abimethod
    def high(self) -> UInt64:
        return five()
""",
    )

    diag_a = await harness.wait_for_diagnostic(doc_a, 1)
    diag_b = await harness.wait_for_diagnostic(doc_b, 1)

    assert (
        diag_a.diagnostics[0].message == "free functions must be annotated with @algopy.subroutine"
    )

    assert (
        diag_b.diagnostics[0].message
        == f"Cannot invoke {a_full_name}.five as it is not decorated with algopy.subroutine"
    )

    harness.insert_lines(
        uri=doc_a,
        lines={
            (1, 25): ", subroutine",
            3: "@subroutine",
        },
    )

    diag_a = await harness.wait_for_diagnostic(doc_a, harness.current_version(doc_a))
    # b was not modified, so the version remains the same,
    # but we expect 2 notifications in total due to it being dependent on a
    diag_b = await harness.wait_for_diagnostic(
        doc_b, harness.current_version(doc_b), num_matches=2
    )

    assert diag_a.diagnostics == []
    assert diag_b.diagnostics == []


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
    diag = await harness.wait_for_diagnostic(unique_uri, 1)

    assert diag.diagnostics[0].message == "cannot encode algopy.UInt64 to algopy.arc4.String"


async def test_non_puyapy_code_is_ignored(
    isolated_harness: "_LanguageServerHarness", unique_uri: str
) -> None:
    isolated_harness.open_doc(
        uri=unique_uri,
        text="""
import sys

print(sys.argv)
""",
    )
    await asyncio.sleep(0.1)
    assert (
        "debug: no algopy related files were changed, nothing to do"
        in isolated_harness.client.stderr
    ), "expected no diagnostics"


@pytest.fixture(scope="module")
def workspace_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("workspace")


@pytest.fixture
def unique_uri(workspace_root: Path) -> str:
    name = str(uuid.uuid4()).replace("-", "")
    unique_path = workspace_root / f"file_{name}.py"
    return unique_path.as_uri()


@pytest_asyncio.fixture(loop_scope="module", scope="module")
async def harness(client: "_LanguageClient", workspace_root: Path) -> "_LanguageServerHarness":
    harness = _LanguageServerHarness(client, workspace_root)
    await harness.initialize()
    return harness


@pytest_asyncio.fixture(loop_scope="module")
async def isolated_harness(workspace_root: Path) -> "_LanguageServerHarness":
    client = await _create_client()
    harness = _LanguageServerHarness(client, workspace_root)
    await harness.initialize()
    return harness


@pytest_asyncio.fixture(loop_scope="module", scope="module")
async def client() -> AsyncIterator["_LanguageClient"]:
    client = await _create_client()
    yield client
    await client.shutdown_async(None)


async def _create_client() -> "_LanguageClient":
    # Find the puya executable path
    puya_path = shutil.which("puyapy-ls")
    assert puya_path is not None, "could not find puyapy-ls executable"
    client = _LanguageClient("puyapy-ls", "99", _LanguageServerProtocol)
    # start the server
    env = os.environ | {"NO_COLOR": "1"}
    await client.start_io(puya_path, "--log-level=debug", env=env)
    return client


class _LanguageServerHarness:
    """Abstracts common LSP interactions between client and server to improve test readability"""

    def __init__(self, client: "_LanguageClient", workspace_root: Path) -> None:
        self.client = client
        self.workspace_root = workspace_root
        self.protocol = typing.cast(_LanguageServerProtocol, client.protocol)
        self._uri_versions = defaultdict[str, int](int)

    def _next_version(self, uri: str) -> int:
        self._uri_versions[uri] += 1
        return self._uri_versions[uri]

    def current_version(self, uri: str) -> int:
        return self._uri_versions[uri]

    async def initialize(self) -> None:
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
                initialization_options={
                    "pythonExecutable": sys.executable,
                    "debounceInterval": 0,
                },
                root_uri=self.workspace_root.as_uri(),
            )
        )
        assert initialized.server_info
        assert initialized.server_info.name == "puyapy"

    def open_doc(self, uri: str, text: str) -> None:
        # create the actual file on disk to so mypy's module discovery continue to work
        path = _uri_to_path(uri)
        assert path is not None
        path.touch()

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

    async def wait_for_diagnostic(
        self, uri: str, version: int, num_matches: int = 1
    ) -> lsp.PublishDiagnosticsParams:
        """Waits until num_matches of diagnostics for the specified document are found"""
        return await asyncio.wait_for(
            self._wait_for_diagnostic(uri, version, num_matches), _DIAGNOSTIC_TIMEOUT
        )

    async def _wait_for_diagnostic(
        self, uri: str, version: int, num_matches: int
    ) -> lsp.PublishDiagnosticsParams:
        # loop until enough matches are found
        while True:
            matching = [
                diag
                for diag in self.protocol.diagnostics
                if diag.uri == uri and diag.version == version
            ]
            if len(matching) >= num_matches:
                break
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self.protocol.diagnostic_event.wait(), 0.1)
        return matching[-1]

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

    async def code_actions(self, unique_uri: str) -> Sequence[lsp.Command | lsp.CodeAction] | None:
        return await self.client.text_document_code_action_async(
            lsp.CodeActionParams(
                text_document=lsp.TextDocumentIdentifier(
                    uri=unique_uri,
                ),
                # get code actions for entire document
                range=lsp.Range(
                    start=lsp.Position(line=0, character=0),
                    end=lsp.Position(line=9999, character=0),
                ),
                context=lsp.CodeActionContext(
                    diagnostics=[],
                ),
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
        self.diagnostics = list[lsp.PublishDiagnosticsParams]()
        self.diagnostic_event = asyncio.Event()

    @lsp_method(lsp.TEXT_DOCUMENT_PUBLISH_DIAGNOSTICS)
    def publish_diagnostics(self, params: lsp.PublishDiagnosticsParams) -> None:
        self.diagnostics.append(params)
        # signal everything waiting on a notification and then reset
        self.diagnostic_event.set()
        self.diagnostic_event.clear()

    @lsp_method(lsp.WINDOW_SHOW_MESSAGE)
    def show_message(self, params: lsp.ShowMessageParams) -> None:
        _client_output(f"{params.type}: {params.message}")


class _LanguageClient(LanguageClient):
    """Override LanguageClient so stderr of service can be forwarded to stdout of test"""

    def __init__(self, *args: typing.Any, **kwargs: typing.Any):
        super().__init__(*args, **kwargs)
        self.stderr = list[str]()
        self.stderr_received = asyncio.Event()

    @typing.override
    async def start_io(self, cmd: str, *args: object, **kwargs: object) -> None:
        await super().start_io(cmd, *args, **kwargs)

        # forward stderr of server process to stdout for visibility when testing
        assert self._server is not None, "expected server to be running"
        stderr = self._server.stderr
        assert stderr is not None, "expected stderr to be defined"
        task = asyncio.create_task(_read_stderr(stderr, self.stderr, self.stderr_received))

        # ensure task reading stderr is cleaned up
        self._async_tasks.append(task)

    @property
    def server(self) -> asyncio.subprocess.Process:
        assert self._server is not None, "no server process"
        return self._server


async def _read_stderr(
    stderr: asyncio.StreamReader, sink: list[str], event: asyncio.Event
) -> None:
    while True:
        try:
            line = await asyncio.wait_for(stderr.readline(), timeout=0.1)
        except TimeoutError:
            continue
        if not line:
            break
        line_utf8 = line.decode("utf8").strip()
        sink.append(line_utf8)
        _server_output(line_utf8, file=sys.stdout)
        event.set()
        event.clear()


def _server_output(msg: str, *, file: TextIO | None = None) -> None:
    _output(f"server: {msg}", file=file)


def _client_output(msg: str, *, file: TextIO | None = None) -> None:
    _output(f"client: {msg}", file=file)


def _output(msg: str, *, file: TextIO | None) -> None:
    time_str = datetime.now(tz=None).strftime("%H:%M:%S.%f").rstrip("0")  # noqa: DTZ005
    print(f"[{time_str}] {msg}", file=file or sys.stdout, flush=True)
