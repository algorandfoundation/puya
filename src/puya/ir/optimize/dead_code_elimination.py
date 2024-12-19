import typing
from collections.abc import Iterable, Sequence, Set

import attrs

from puya import log
from puya.context import CompileContext
from puya.errors import InternalError
from puya.ir import models, visitor
from puya.ir._utils import bfs_block_order
from puya.ir.ssa import TrivialPhiRemover
from puya.utils import StableSet

logger = log.get_logger(__name__)


PURE_AVM_OPS = frozenset(
    [
        # group: ops that can't fail at runtime
        # `txn FirstValidTime` technically could fail, but shouldn't happen on mainnet?
        "txn",
        "sha256",
        "keccak256",
        "sha3_256",
        "sha512_256",
        "bitlen",
        # group: could only fail on a type error
        "!",
        "!=",
        "&",
        "&&",
        "<",
        "<=",
        "==",
        ">",
        ">=",
        "|",
        "||",
        "~",
        "addw",
        "mulw",
        "itob",
        "len",
        "select",
        "sqrt",
        "shl",
        "shr",
        # group: fail if an input is zero
        "%",
        "/",
        "expw",
        "divmodw",
        "divw",
        # group: fail on over/underflow
        "*",
        "+",
        "-",
        "^",
        "exp",
        # group: fail on index out of bounds
        "arg",
        "arg_0",
        "arg_1",
        "arg_2",
        "arg_3",
        "args",
        "extract",
        "extract3",
        "extract_uint16",
        "extract_uint32",
        "extract_uint64",
        "replace2",
        "replace3",
        "setbit",
        "setbyte",
        "getbit",
        "getbyte",
        "gaid",
        "gaids",
        "gload",
        "gloads",
        "gloadss",
        "substring",
        "substring3",
        "txna",
        "txnas",
        "gtxn",
        "gtxna",
        "gtxnas",
        "gtxns",
        "gtxnsa",
        "gtxnsas",
        "block",
        # group: fail on input too large
        "b%",
        "b*",
        "b+",
        "b-",
        "b/",
        "b^",
        "btoi",
        # group: might fail on input too large? TODO: verify these
        "b!=",
        "b<",
        "b<=",
        "b==",
        "b>",
        "b>=",
        "b&",
        "b|",
        "b~",
        "bsqrt",
        # group: fail on output too large
        "concat",
        "bzero",
        # group: fail on input format / byte lengths
        "base64_decode",
        "json_ref",
        "ecdsa_pk_decompress",
        "ecdsa_pk_recover",
        "ec_add",
        "ec_pairing_check",
        "ec_scalar_mul",
        "ec_subgroup_check",
        "ec_multi_scalar_mul",
        "ec_map_to",
        "ecdsa_verify",
        "ed25519verify",
        "ed25519verify_bare",
        "vrf_verify",
        # group: v11
        "falcon_verify",
        "sumhash512",
    ]
)

# ops that have no observable side effects outside the function
# note: originally generated basd on all ops that:
#       - return a stack value (this, as of v10, yields no false negatives)
#       - AND isn't in the generate_avm_ops.py list of exclusions (which are all control flow
#             or pure stack manipulations)
#       - AND isn't box_create or box_del, they were the only remaining false positives
IMPURE_SIDE_EFFECT_FREE_AVM_OPS = frozenset(
    [
        # group: ops that can't fail at runtime
        "global",  # OpcodeBudget is non-const, otherwise this could be pure
        # group: could only fail on a type error
        "app_global_get",
        "app_global_get_ex",
        "load",
        # group: fail on resource not "available"
        # TODO: determine if any of this group is pure
        "acct_params_get",
        "app_opted_in",
        "app_params_get",
        "asset_holding_get",
        "asset_params_get",
        "app_local_get",
        "app_local_get_ex",
        "balance",
        "min_balance",
        "box_extract",
        "box_get",
        "box_len",
        # group: fail on index out of bounds
        "loads",
        # group: might fail depending on state
        "itxn",
        "itxna",
        "itxnas",
        "gitxn",
        "gitxna",
        "gitxnas",
    ]
)

_should_be_empty = PURE_AVM_OPS & IMPURE_SIDE_EFFECT_FREE_AVM_OPS
assert not _should_be_empty, _should_be_empty
SIDE_EFFECT_FREE_AVM_OPS = frozenset([*PURE_AVM_OPS, *IMPURE_SIDE_EFFECT_FREE_AVM_OPS])


@attrs.define
class SubroutineCollector(visitor.IRTraverser):
    subroutines: StableSet[models.Subroutine] = attrs.field(factory=StableSet)

    @classmethod
    def collect(cls, program: models.Program) -> StableSet[models.Subroutine]:
        collector = cls()
        collector.visit_subroutine(program.main)
        return collector.subroutines

    def visit_subroutine(self, subroutine: models.Subroutine) -> None:
        if subroutine not in self.subroutines:
            self.subroutines.add(subroutine)
            self.visit_all_blocks(subroutine.body)

    def visit_invoke_subroutine(self, callsub: models.InvokeSubroutine) -> None:
        self.visit_subroutine(callsub.target)


def remove_unused_subroutines(program: models.Program) -> bool:
    subroutines = SubroutineCollector.collect(program)
    if modified := (len(subroutines) != (1 + len(program.subroutines))):
        to_keep = [p for p in program.subroutines if p in subroutines]
        for p in program.subroutines:
            if p not in subroutines:
                logger.debug(f"removing unused subroutine {p.id}")
        program.subroutines = to_keep
    return modified


def remove_unused_variables(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    modified = 0
    assignments = dict[tuple[models.BasicBlock, models.Assignment], set[models.Register]]()
    for block, op, register in UnusedRegisterCollector.collect(subroutine):
        if isinstance(op, models.Assignment):
            assignments.setdefault((block, op), set()).add(register)
        else:
            assert register == op.register
            block.phis.remove(op)
            logger.debug(f"Removing unused variable {register.local_id}")
            modified += 1

    for (block, ass), registers in assignments.items():
        if registers.symmetric_difference(ass.targets):
            pass  # some registers still used
        elif isinstance(ass.source, models.Value | models.InnerTransactionField) or (
            isinstance(ass.source, models.Intrinsic)
            and ass.source.op.code in SIDE_EFFECT_FREE_AVM_OPS
        ):
            for reg in sorted(registers, key=lambda r: r.local_id):
                logger.debug(f"Removing unused variable {reg.local_id}")
            block.ops.remove(ass)
            modified += 1
        else:
            logger.debug(
                f"Not removing unused assignment since source is not marked as pure: {ass}"
            )
    return modified > 0


@attrs.define(kw_only=True)
class UnusedRegisterCollector(visitor.IRTraverser):
    used: set[models.Register] = attrs.field(factory=set)
    assigned: dict[models.Register, tuple[models.BasicBlock, models.Assignment | models.Phi]] = (
        attrs.field(factory=dict)
    )
    active_block: models.BasicBlock

    @classmethod
    def collect(
        cls, sub: models.Subroutine
    ) -> Iterable[tuple[models.BasicBlock, models.Assignment | models.Phi, models.Register]]:
        collector = cls(active_block=sub.entry)
        collector.visit_all_blocks(sub.body)
        for reg, (block, ass) in collector.assigned.items():
            if reg not in collector.used:
                yield block, ass, reg

    @typing.override
    def visit_block(self, block: models.BasicBlock) -> None:
        self.active_block = block
        super().visit_block(block)

    @typing.override
    def visit_assignment(self, ass: models.Assignment) -> None:
        for target in ass.targets:
            self.assigned[target] = (self.active_block, ass)
        ass.source.accept(self)

    @typing.override
    def visit_phi(self, phi: models.Phi) -> None:
        # don't visit phi.register, as this would mean the phi can never be considered unused
        for arg in phi.args:
            arg.accept(self)
        self.assigned[phi.register] = (self.active_block, phi)

    @typing.override
    def visit_register(self, reg: models.Register) -> None:
        self.used.add(reg)


def remove_unreachable_blocks(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    reachable_set = frozenset(bfs_block_order(subroutine.entry))
    unreachable_blocks = [b for b in subroutine.body if b not in reachable_set]
    if not unreachable_blocks:
        return False

    logger.debug(f"Removing unreachable blocks: {', '.join(map(str, unreachable_blocks))}")

    reachable_blocks = []
    for block in subroutine.body:
        if block in reachable_set:
            reachable_blocks.append(block)
            if not reachable_set.issuperset(block.successors):
                raise InternalError(
                    f"Block {block} has unreachable successor(s),"
                    f" but was not marked as unreachable itself"
                )
            if not reachable_set.issuperset(block.predecessors):
                block.predecessors = [b for b in block.predecessors if b in reachable_set]
                logger.debug(f"Removed unreachable predecessors from {block}")

    UnreachablePhiArgsRemover.apply(unreachable_blocks, reachable_blocks)
    subroutine.body = reachable_blocks
    return True


@attrs.define
class UnreachablePhiArgsRemover(visitor.IRTraverser):
    _unreachable_blocks: Set[models.BasicBlock]
    _reachable_blocks: Sequence[models.BasicBlock]

    @classmethod
    def apply(
        cls,
        unreachable_blocks: Sequence[models.BasicBlock],
        reachable_blocks: Sequence[models.BasicBlock],
    ) -> None:
        collector = cls(frozenset(unreachable_blocks), reachable_blocks)
        collector.visit_all_blocks(reachable_blocks)

    def visit_phi(self, phi: models.Phi) -> None:
        args_to_remove = [a for a in phi.args if a.through in self._unreachable_blocks]
        if not args_to_remove:
            return
        logger.debug(
            "Removing unreachable phi arguments: " + ", ".join(sorted(map(str, args_to_remove)))
        )
        phi.args = [a for a in phi.args if a not in args_to_remove]
        if not phi.non_self_args:
            raise InternalError(
                f"undefined phi created when removing args through "
                f"{', '.join(map(str, self._unreachable_blocks))}"
            )
        TrivialPhiRemover.try_remove(phi, self._reachable_blocks)
