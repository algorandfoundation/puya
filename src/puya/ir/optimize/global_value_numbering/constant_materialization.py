from collections.abc import Mapping

from puya import log
from puya.avm_encoding import encode_bytes, encode_varuint
from puya.errors import InternalError
from puya.ir import models
from puya.ir._utils import bfs_block_order, get_bytes_constant
from puya.ir.optimize._intrinsics import COMPILE_TIME_CONSTANT_OPS
from puya.ir.optimize._utils import SSAReadTracker
from puya.ir.optimize.global_value_numbering.tables import BytesConstKey, GVNTables, UInt64ConstKey
from puya.utils import is_list_of, unique

__all__ = [
    "materialize_constants",
]

logger = log.get_logger(__name__)


def materialize_constants(
    tables: GVNTables,
    subroutine: models.Subroutine,
    start: models.BasicBlock,
    ssa_reads: SSAReadTracker,
    *,
    expand_all_bytes: bool,
) -> bool:
    modified = False
    defining_op = {
        target: op
        for block in subroutine.body
        for op in block.ops
        if isinstance(op, models.Assignment)
        for target in op.targets
    }
    for block in bfs_block_order(start):
        for op in block.ops:
            if not isinstance(op, models.Assignment):
                continue
            if isinstance(op.source, models.MultiValue):
                continue
            materialized = try_materialize_constants(
                op, tables, ssa_reads, defining_op, expand_all_bytes=expand_all_bytes
            )
            if materialized is not None:
                modified = True
                with ssa_reads.update(op):
                    op.source = materialized
    return modified


def try_materialize_constants(
    op: models.Assignment,
    tables: GVNTables,
    ssa_reads: SSAReadTracker,
    defining_op: Mapping[models.Register, models.Assignment],
    *,
    expand_all_bytes: bool,
) -> models.MultiValue | None:
    target_vns = [tables.register_vn[t] for t in op.targets]
    target_defns = [tables.vn_definition.get(vn) for vn in target_vns]
    if len(target_defns) == 1:
        (target_defn,) = target_defns
        (source_type,) = op.source.types
        match target_defn:
            case UInt64ConstKey(value=uint64_const):
                return models.UInt64Constant(
                    value=uint64_const,
                    ir_type=source_type,
                    source_location=op.source.source_location,
                )
            case BytesConstKey(value=bytes_const, encoding=bytes_encoding) if expand_all_bytes or (
                isinstance(op.source, models.Intrinsic)
                and (
                    len(encode_bytes(bytes_const))
                    <= intrinsic_dead_cost(op, op.source, ssa_reads, defining_op)
                )
            ):
                return models.BytesConstant(
                    value=bytes_const,
                    encoding=bytes_encoding,
                    ir_type=source_type,
                    source_location=op.source.source_location,
                )
    elif is_list_of(target_defns, UInt64ConstKey):
        return models.ValueTuple(
            values=[
                models.UInt64Constant(
                    value=uint64_defn.value,
                    ir_type=source_type,
                    source_location=op.source.source_location,
                )
                for uint64_defn, source_type in zip(target_defns, op.source.types, strict=True)
            ],
            source_location=op.source_location,
        )

    return None


def intrinsic_dead_cost(
    op: models.Assignment,
    source: models.Intrinsic,
    ssa_reads: SSAReadTracker,
    defining_op: Mapping[models.Register, models.Assignment],
) -> int:
    cost = intrinsic_cost(source)
    for reg in unique(a for a in source.args if isinstance(a, models.Register)):
        if ssa_reads.is_sole_usage(reg, op):
            defn = defining_op.get(reg)
            if defn is None or len(defn.targets) != 1:
                continue
            match defn.source:
                case models.Intrinsic() as inner if inner.op in COMPILE_TIME_CONSTANT_OPS:
                    cost += intrinsic_dead_cost(defn, inner, ssa_reads, defining_op)
                case models.Constant() as const:
                    cost += get_const_size(const)
    return cost


def intrinsic_cost(intrinsic: models.Intrinsic) -> int:
    instr_size = intrinsic.op.size
    const_arg_sizes = sum(
        get_const_size(arg) for arg in intrinsic.args if isinstance(arg, models.Constant)
    )
    return instr_size + const_arg_sizes


def get_const_size(arg: models.Constant) -> int:
    bytes_const = get_bytes_constant(arg)
    if bytes_const is not None:
        return len(encode_bytes(bytes_const))
    match arg:
        case models.ITxnConstant():
            return 0  # immediates get counted as part of op
        case models.SlotConstant():
            raise InternalError("slot constant should not appear in IR during optimisation")
        case models.UInt64Constant(value=int_value):
            return len(encode_varuint(int_value))
    logger.debug(f"GVN: unhandled constant type {type(arg).__name__}")
    return 0
