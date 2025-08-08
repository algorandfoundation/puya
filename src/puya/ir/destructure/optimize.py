import contextlib
import itertools

from puya import log
from puya.errors import InternalError
from puya.ir import models
from puya.ir.optimize.collapse_blocks import BlockReferenceReplacer
from puya.utils import not_none, unique

logger = log.get_logger(__name__)


def post_ssa_optimizer(sub: models.Subroutine, optimization_level: int) -> None:
    logger.debug(f"Performing post-SSA optimizations at level {optimization_level}")
    if optimization_level >= 1:
        _remove_linear_jumps(sub)
    if optimization_level >= 2:
        _block_deduplication(sub)
    if optimization_level >= 1:
        _lift_returns(sub)


def _remove_linear_jumps(subroutine: models.Subroutine) -> None:
    #  P = {p0, p1, ..., pn} -> {j} -> {t}
    # remove {j} from subroutine
    # point P at t:
    #  update references within P from j to t
    #  ensure P are all in predecessors of t
    # This exists here and not in main IR optimization loop because we only want to do it for
    # blocks that are _truly_ empty, not ones that contain phi-node magic that results in copies
    # build a map of any blocks that are just an unconditional branch to their targets
    jumps = dict[models.BasicBlock, models.BasicBlock]()
    for block in subroutine.body.copy():
        match block:
            case models.BasicBlock(
                ops=[], terminator=models.Goto(target=target)
            ) if target is not block:
                jumps[block] = target
                logger.debug(f"Removing jump block {block}")
                with contextlib.suppress(ValueError):
                    target.predecessors.remove(block)
                subroutine.body.remove(block)

    # now back-propagate any chains
    replacements = dict[models.BasicBlock, models.BasicBlock]()
    for src, target in jumps.items():
        while True:
            try:
                target = jumps[target]
            except KeyError:
                break
        logger.debug(f"branching to {src} will be replaced with {target}")
        replacements[src] = target
        BlockReferenceReplacer.apply(find=src, replacement=target, blocks=subroutine.body)
        for pred in src.predecessors:
            if pred not in target.predecessors:
                target.predecessors.append(pred)


def _block_deduplication(subroutine: models.Subroutine) -> None:
    seen = dict[tuple[object, ...], models.BasicBlock]()
    for block in subroutine.body.copy():
        all_ops = tuple(op.freeze() for op in block.all_ops)
        if existing := seen.get(all_ops):
            logger.debug(
                f"Removing duplicated block {block} and updating references to {existing}"
            )
            BlockReferenceReplacer.apply(find=block, replacement=existing, blocks=subroutine.body)
            subroutine.body.remove(block)
            existing.predecessors = unique(
                itertools.chain(existing.predecessors, block.predecessors)
            )
        else:
            seen[all_ops] = block


def _lift_returns(subroutine: models.Subroutine) -> None:
    next_tmp_id = None
    for block in subroutine.body:
        successors = block.successors
        if len(successors) <= 1 or block in successors:
            continue
        terminator = not_none(block.terminator)
        try:
            (single_pair,) = {
                (_get_constant_return(not_none(t.terminator)), tuple(t.predecessors))
                for t in successors
                if type(t.terminator) is not models.Fail
            }
            sole_constant_return_or_none, (single_pred,) = single_pair
        except ValueError:
            continue
        assert single_pred.terminator is terminator
        if sole_constant_return_or_none is None:
            continue
        value = sole_constant_return_or_none
        our_tmp_prefix = f"lifted{models.TMP_VAR_INDICATOR}"

        if next_tmp_id is None:
            next_tmp_id = max(
                (
                    int(r.name.split(models.TMP_VAR_INDICATOR)[1])
                    for r in subroutine.get_assigned_registers()
                    if r.name.startswith(our_tmp_prefix)
                ),
                default=-1,
            )
        next_tmp_id += 1
        target = models.Register(
            ir_type=value.ir_type,
            name=f"{our_tmp_prefix}{next_tmp_id}",
            version=0,
            source_location=value.source_location,
        )
        lifted_assignment = models.Assignment(
            source=value,
            targets=[target],
            source_location=value.source_location,
        )
        block.ops.insert(0, lifted_assignment)
        for succ in successors:
            match succ.terminator:
                case models.SubroutineReturn(result=[_]):
                    succ.terminator.result[:] = [target]
                case models.ProgramExit():
                    succ.terminator.result = target
                case models.Fail():
                    pass
                case _:
                    raise InternalError(
                        f"unhandled terminator node for lifting: {type(succ.terminator).__name__}",
                        succ.source_location,
                    )


def _get_constant_return(t: models.ControlOp) -> models.Constant | None:
    match t:
        case models.SubroutineReturn(result=[value]):
            pass
        case models.ProgramExit(result=value):
            pass
        case _:
            return None
    if not isinstance(value, models.Constant):
        return None
    return value
