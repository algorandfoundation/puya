import pytest

from puya.compilation_artifacts import CompiledContract, CompiledLogicSig
from puya.ussemble.assemble import _apply_autosalt, _program_hash_on_curve
from puya.ussemble.op_spec import OP_SPECS
from tests import TEST_CASES_DIR
from tests.utils import PuyaTestCase
from tests.utils.compile import compile_from_test_case

_INTCBLOCK = OP_SPECS["intcblock"].code

# (name, program, expected) copied verbatim from go-algorand's TestAssemblerIntcblockSalt and
# TestPragmaAutosalt assertions; expected == program means no salt is added.
_GO_ALGORAND_SALT_VECTORS = [
    (
        "trailing intcblock (v13 pushint 12)",
        bytes.fromhex("0d810c"),
        bytes.fromhex("0d810c200100"),  # salt byte 0
    ),
    (
        "manual intcblock (v13 intcblock 0; intc_0)",
        bytes.fromhex("0d20010022"),
        bytes.fromhex("0d20010022200102"),  # salt byte 2, body intcblock left unchanged
    ),
    (
        "already off-curve is unchanged (v13 byte 0x01; app_global_get; pop; pushint 1)",
        bytes.fromhex("0d80010164488101"),
        bytes.fromhex("0d80010164488101"),
    ),
]


@pytest.mark.parametrize(
    "case", _GO_ALGORAND_SALT_VECTORS, ids=[v[0] for v in _GO_ALGORAND_SALT_VECTORS]
)
def test_salt_matches_go_algorand_vectors(case: tuple[str, bytes, bytes]) -> None:
    _name, program, expected = case
    assert _program_hash_on_curve(program) is (program != expected)
    assert _apply_autosalt(program) == expected
    assert not _program_hash_on_curve(expected)


@pytest.fixture(scope="module")
def programs() -> dict[str, bytes]:
    """Bytecode of every program in test_cases/autosalt, contracts keyed as <name>.<kind>."""
    result = compile_from_test_case(
        PuyaTestCase(TEST_CASES_DIR / "autosalt"),
        optimization_level=1,
        debug_level=0,
        output_bytecode=True,
    )
    compiled = dict[str, bytes]()
    for artifact in result.teal:
        if isinstance(artifact, CompiledLogicSig):
            named = {artifact.metadata.name: artifact.program}
        else:
            assert isinstance(artifact, CompiledContract)
            named = {
                f"{artifact.metadata.name}.approval": artifact.approval_program,
                f"{artifact.metadata.name}.clear": artifact.clear_program,
            }
        for name, program in named.items():
            assert program.bytecode is not None
            compiled[name] = program.bytecode
    return compiled


def _assert_trailing_salt(salted: bytes, unsalted: bytes) -> None:
    """The salted program is the on-curve unsalted one plus a trailing `intcblock 1 <salt>`
    making it off-curve."""
    assert _program_hash_on_curve(unsalted)
    assert salted[: len(unsalted)] == unsalted
    assert salted[len(unsalted) : -1] == bytes((_INTCBLOCK, 1))
    assert salted[-1] < 0x80  # the salt is a single-byte varint
    assert not _program_hash_on_curve(salted)


@pytest.mark.parametrize("suffix", ["", "_v12"], ids=["v13", "v12"])
def test_logicsig_salting(programs: dict[str, bytes], suffix: str) -> None:
    # the opt-out is the on-curve unsalted baseline (its programs were chosen to hash on-curve)...
    unsalted = programs[f"no_salt_sig{suffix}"]
    assert _program_hash_on_curve(unsalted)
    # ...while both the default and an explicit autosalt=True salt on any version
    _assert_trailing_salt(programs[f"default_sig{suffix}"], unsalted)
    _assert_trailing_salt(programs[f"force_salt_sig{suffix}"], unsalted)


# the on-curve cells are where "never salted by default" is demonstrated (an off-curve program is
# left alone regardless of any autosalt setting) and where forcing autosalt appends a real salt
@pytest.mark.parametrize(
    ("version", "kind", "default_on_curve"),
    [
        ("", "approval", False),
        ("", "clear", True),
        ("V12", "approval", True),
        ("V12", "clear", False),
    ],
    ids=["v13-approval", "v13-clear", "v12-approval", "v12-clear"],
)
def test_contract_salting(
    programs: dict[str, bytes], version: str, kind: str, *, default_on_curve: bool
) -> None:
    # the contracts all share the same body, so the default programs are the unsalted baselines
    default = programs[f"DefaultContract{version}.{kind}"]
    assert _program_hash_on_curve(default) is default_on_curve
    # an explicit opt-out is identical to the default (contracts are never salted by default)
    assert programs[f"UnsaltedContract{version}.{kind}"] == default
    # while forcing autosalt salts an on-curve program on any version, and is otherwise a no-op
    salted = programs[f"SaltedContract{version}.{kind}"]
    if default_on_curve:
        _assert_trailing_salt(salted, default)
    else:
        assert salted == default
