import attrs

from puya import log
from puya.context import CompileContext
from puya.ir import models
from puya.ir.avm_ops import AVMOp
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


@attrs.frozen
class _Replace:
    src: models.Value
    index: models.Value | int
    replacement: models.Value


@attrs.frozen
class _Extract:
    ass: models.Assignment
    op: models.Intrinsic
    src: models.Value
    index: models.Value | int
    length: models.Value | int


def remove_box_exists(block: models.BasicBlock) -> bool:
    #   for any box op that returns an exist flag that is asserted
    #   can remove any asserts after the first one as long as the box register is the same
    #   and no box_del op is called
    #   begin block | subroutine call
    #       exist state of all box keys are unknown
    #   box_create | box_extract | box_put | box_replace | box_resize | box_splice key
    #       set box key as known to exist
    #   box_del key
    #       sett box key as known to not exist
    #   box_get | box_len
    #       if unknown if box exists then keep the assert, assume box exists after assert
    #       if known that box exists then remove any asserts
    #       if known that box does not exist then replace asserts with err

    modified = False
    box_exists = dict[models.Value, bool]()

    box_exists_regs = dict[models.Value, models.Value]()
    for op in block.ops.copy():
        maybe_ass = None
        if isinstance(op, models.Assignment):
            maybe_ass = op
            maybe_intrinsic: models.IRVisitable = op.source
        else:
            maybe_intrinsic = op
        if isinstance(maybe_intrinsic, models.Intrinsic):
            if maybe_intrinsic.op in (
                AVMOp.box_create,
                AVMOp.box_extract,
                AVMOp.box_put,
                AVMOp.box_replace,
                AVMOp.box_resize,
                AVMOp.box_splice,
            ):
                box_key = maybe_intrinsic.args[0]
                box_exists[box_key] = True
            elif maybe_intrinsic.op == AVMOp.box_del:
                # conservative assume could be deleting any box
                box_exists.clear()
            elif maybe_ass and maybe_intrinsic.op in (AVMOp.box_get, AVMOp.box_len):
                box_key = maybe_intrinsic.args[0]
                _, exists_reg = maybe_ass.targets
                box_exists_regs[exists_reg] = box_key
            elif (
                maybe_intrinsic.op == AVMOp.assert_
                and (box_exists_reg := maybe_intrinsic.args[0]) in box_exists_regs
            ):
                box_key = box_exists_regs[box_exists_reg]
                try:
                    box_does_exist = box_exists[box_key]
                except KeyError:
                    # current state of box is unknown, but can assume it exists after this op
                    box_exists[box_key] = True
                    continue
                if box_does_exist:
                    logger.debug(
                        f"box_key {box_key} is known to exist, removing assert",
                        location=op.source_location,
                    )
                    # box exists, so can remove assert
                    block.ops.remove(op)
                    modified = True
        elif isinstance(maybe_intrinsic, models.InvokeSubroutine):
            box_exists.clear()
    return modified


def minimize_box_exist_asserts(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    modified = False
    for block in subroutine.body:
        modified = remove_box_exists(block) or modified
    return modified


def minimize_box_access(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    # map of box read value -> read op
    box_gets = dict[models.Register, tuple[models.Intrinsic, models.Assignment]]()
    box_puts = list[tuple[models.Intrinsic, models.BasicBlock]]()
    # map of replace registers -> replace params
    replaces = dict[models.Register, _Replace]()
    # map of extract registers -> extract params
    extracts = dict[models.Register, _Extract]()

    #   TODO: optimize repeated extracts
    #   TODO: optimize repeated replace

    for block in subroutine.body:
        for op in block.ops:
            # collect ops related to box read/write
            if isinstance(op, models.Intrinsic) and op.op == AVMOp.box_put:
                box_puts.append((op, block))
            elif isinstance(op, models.Assignment):
                if not isinstance(op.source, models.Intrinsic):
                    continue
                op_code = op.source.op
                args = op.source.args
                imm = op.source.immediates
                if op_code == AVMOp.box_get:
                    maybe_value, exists = op.targets
                    box_gets[maybe_value] = op.source, op
                elif op_code == AVMOp.replace2:
                    (target,) = op.targets
                    index_imm = imm[0]
                    assert isinstance(index_imm, int)
                    src, replacement = args
                    replaces[target] = _Replace(
                        src=src,
                        index=index_imm,
                        replacement=replacement,
                    )
                elif op_code == AVMOp.replace3:
                    (target,) = op.targets
                    src, index, replacement = args
                    replaces[target] = _Replace(
                        src=src,
                        index=index,
                        replacement=replacement,
                    )
                elif op_code == AVMOp.extract3:
                    (target,) = op.targets
                    src, index, length = args
                    extracts[target] = _Extract(
                        ass=op,
                        op=op.source,
                        src=src,
                        index=index,
                        length=length,
                    )
                elif op_code == AVMOp.extract and imm[1] != 0:
                    (target,) = op.targets
                    index_imm, length_imm = imm
                    assert isinstance(index_imm, int)
                    assert isinstance(length_imm, int)
                    (src,) = args
                    extracts[target] = _Extract(
                        ass=op,
                        op=op.source,
                        src=src,
                        index=index_imm,
                        length=length_imm,
                    )
    modified = False
    for extract in extracts.values():
        try:
            box_get, box_get_block = box_gets[extract.src]  # type: ignore[index]
        except KeyError:
            continue
        (box_get_key,) = box_get.args

        # have found a box_get -> extract
        # can replace this with the more efficient box_extract
        index = _as_uint64(extract.index, extract.op.source_location)
        length = _as_uint64(extract.length, extract.op.source_location)
        logger.debug(
            f"transforming `box_get {box_get_key}; extract` into `box_extract`",
            location=extract.ass.source_location,
        )
        extract.ass.source = models.Intrinsic(
            op=AVMOp.box_extract,
            args=[box_get_key, index, length],
            source_location=extract.op.source_location,
        )
        modified = True
    for box_put, put_block in box_puts:
        box_put_key, box_put_value = box_put.args
        try:
            replace = replaces[box_put_value]  # type: ignore[index]
        except KeyError:
            continue
        try:
            box_get, _ = box_gets[replace.src]  # type: ignore[index]
        except KeyError:
            continue
        (box_get_key,) = box_get.args
        # TODO: also check box has not been deleted
        if box_get_key == box_put_key:
            # have found a box_get -> replace -> box_put
            # can replace this with the more efficient box_replace
            index = _as_uint64(replace.index, box_put.source_location)
            logger.debug(
                f"transforming `replace; box_put {box_put_key}` into `box_replace`",
                location=box_put.source_location,
            )
            box_replace = models.Intrinsic(
                op=AVMOp.box_replace,
                args=[box_put_key, index, replace.replacement],
                source_location=box_put.source_location,
            )
            put_index = put_block.ops.index(box_put)
            put_block.ops[put_index] = box_replace
            modified = True
    return modified


def _as_uint64(value: models.Value | int, loc: SourceLocation | None) -> models.Value:
    if isinstance(value, int):
        return models.UInt64Constant(value=value, source_location=loc)
    else:
        return value
