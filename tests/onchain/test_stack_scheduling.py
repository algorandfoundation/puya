import pytest

from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer

_TEST_CASE = TEST_CASES_DIR / "stack_scheduling"


def test_op_prefix_concat(deployer_o: Deployer) -> None:
    arg = b"hello"
    response = deployer_o.create_bare((_TEST_CASE, "OpPrefixConcat"), args=[arg])

    assert response.logs == [(1).to_bytes(8, "big") + arg]


@pytest.mark.parametrize(
    "args",
    [
        (b"a", b"b", b"c"),
        (),
    ],
)
def test_const_prefix_concat(deployer_o: Deployer, args: tuple[bytes, ...]) -> None:
    response = deployer_o.create_bare((_TEST_CASE, "ConstPrefixConcat"), args=args)

    assert response.logs == [b"log:" + len(args).to_bytes(8, "big")]


def test_local_var_concat(deployer_o: Deployer) -> None:
    args = (b"x:", b"a:", b"b:")
    response = deployer_o.create_bare((_TEST_CASE, "LocalVarConcat"), args=args)

    assert response.logs == [args[0] + (args[1] + args[2])]


def test_local_var_concat_right(deployer_o: Deployer) -> None:
    args = (b"x:", b"a:", b"b:")
    response = deployer_o.create_bare((_TEST_CASE, "VarConcatRight"), args=args)

    assert response.logs == [(args[1] + args[2]) + args[0]]


def test_frame_slot_mutation_concat(deployer_o: Deployer) -> None:
    args = (b"hello", b"world")
    response = deployer_o.create_bare((_TEST_CASE, "FrameSlotMutationConcat"), args=args)

    expected = args[1] + (args[0] + args[1])
    assert response.logs == [expected]


@pytest.mark.parametrize(
    "args",
    [
        (b"one", b"two", b"three"),
        (b"solo",),
        (),
    ],
)
def test_frame_mutate_in_loop_concat(deployer_o: Deployer, args: tuple[bytes, ...]) -> None:
    response = deployer_o.create_bare((_TEST_CASE, "FrameMutateInLoopConcat"), args=args)

    expected = b"".join(b"," + a for a in args)
    assert response.logs == [expected]


def test_deep_shuffle_concat(deployer_o: Deployer) -> None:
    args = (b"a", b"b", b"c", b"d")
    response = deployer_o.create_bare((_TEST_CASE, "DeepShuffleConcat"), args=args)

    expected = b"prefix:" + (args[0] + args[1]) + (args[2] + args[3])
    assert response.logs == [expected]


def test_duped_local_concat(deployer_o: Deployer) -> None:
    args = (b"X", b"Y")
    response = deployer_o.create_bare((_TEST_CASE, "DupedLocalConcat"), args=args)

    assert response.logs == [args[0] + args[1] + args[0] + args[1]]


@pytest.mark.parametrize(
    "args",
    [
        (b"a", b"b"),
        (b"a", b"b", b"c"),
    ],
)
def test_int_local_shuffle_concat(deployer_o: Deployer, args: tuple[bytes, ...]) -> None:
    response = deployer_o.create_bare((_TEST_CASE, "IntLocalShuffleConcat"), args=args)

    n = len(args)
    expected = [n.to_bytes(8, "big") + args[0] + args[1]]
    if n > 1:
        expected.append((n + 1).to_bytes(8, "big") + args[1] + args[0])
    assert response.logs == expected


def test_scratch_load_shuffle_concat(deployer_o: Deployer) -> None:
    args = (b"hello", b"world")
    response = deployer_o.create_bare((_TEST_CASE, "ScratchLoadShuffleConcat"), args=args)

    n_bytes = len(args).to_bytes(8, "big")
    assert response.logs == [args[0] + n_bytes]


def test_scratch_load_barrier_concat(deployer_o: Deployer) -> None:
    args = (b"hello", b"world")
    response = deployer_o.create_bare((_TEST_CASE, "ScratchLoadBarrierConcat"), args=args)

    n_bytes = len(args).to_bytes(8, "big")
    assert response.logs == [args[1] + n_bytes]


@pytest.mark.parametrize(
    "args",
    [
        (b"first", b"second"),
        (b"first", b"second", b"third"),
    ],
)
def test_subroutine_param_swap_concat(deployer_o: Deployer, args: tuple[bytes, ...]) -> None:
    response = deployer_o.create_bare((_TEST_CASE, "SubroutineParamSwapConcat"), args=args)

    if len(args) > 2:
        a, b = args[1], args[2]
    else:
        a, b = args[0], args[1]
    assert response.logs == [a + b + a]
