import itertools
import typing
from collections.abc import Callable, Iterable
from copy import deepcopy

import attrs
import structlog.typing

from puya.context import CompileContext
from puya.ir import models
from puya.ir.builder import TMP_VAR_INDICATOR

logger: structlog.typing.FilteringBoundLogger = structlog.get_logger(__name__)

_T = typing.TypeVar("_T")


def sequentialize(
    copies: Iterable[tuple[_T, _T]],
    mktmp: Callable[[_T], _T],
    *,
    filter_dup_dests: bool = True,
    allow_fan_out: bool = True,
) -> list[tuple[_T, _T]]:
    # If filter_dup_dests is True, consider pairs ordered, and if multiple
    # pairs have the same dest var, the last one takes effect. Otherwise,
    # such duplicate dest vars is an error.
    if filter_dup_dests:
        # If there're multiple assignments to the same var, keep only the latest
        copies = list(dict(copies).items())

    ready = []
    to_do = []
    pred = {}
    loc = dict[_T, _T | None]()
    res = []

    for b, _ in copies:
        loc[b] = None

    for b, a in copies:
        loc[a] = a
        pred[b] = a

        # Extra check
        if not filter_dup_dests and b in to_do:
            raise ValueError(f"Conflicting assignments to destination {b}, latest: {(b, a)}")

        to_do.append(b)

    for b, _ in copies:
        if loc[b] is None:
            ready.append(b)

    logger.debug("loc: %s", "{" + ", ".join(f"{k}={v}" for k, v in loc.items()) + "}")
    logger.debug("pred: %s", "{" + ", ".join(f"{k}={v}" for k, v in pred.items()) + "}")
    logger.debug("ready: %s", ", ".join(map(str, ready)))
    logger.debug("to_do: %s", ", ".join(map(str, to_do)))

    while to_do:
        while ready:
            b = ready.pop()
            logger.debug("* avail %s", b)
            if b not in pred:
                continue
            a = pred[b]
            c = loc[a]
            assert c is not None
            # print("%s <- %s" % (b, a))
            res.append((b, c))

            # Addition by Paul Sokolovsky to handle fan-out case (when same
            # source is assigned to multiple destinations).
            if allow_fan_out and c in to_do:
                to_do.remove(c)

            loc[a] = b
            if a == c:
                ready.append(a)

        # Addition to handle fan-out.
        if allow_fan_out and not to_do:
            break

        b = to_do.pop()
        logger.debug("* to_do %s", b)
        if b != loc[pred[b]]:
            tmp = mktmp(b)
            # print("%s <- %s" % (b, a))
            res.append((tmp, b))
            loc[b] = tmp
            ready.append(b)

    return res


def _impl(sub: models.Subroutine) -> None:
    our_tmp_prefix = f"parcopy{TMP_VAR_INDICATOR}"
    max_tmp_id = max(
        (
            int(r.name.split(TMP_VAR_INDICATOR)[1])
            for r in sub.get_assigned_registers()
            if r.name.startswith(our_tmp_prefix)
        ),
        default=-1,
    )
    next_tmp_id = itertools.count(max_tmp_id + 1)

    def make_temp(x: models.Value | models.Register) -> models.Register:
        return models.Register(
            atype=x.atype,
            name=f"{our_tmp_prefix}{next(next_tmp_id)}",
            version=0,
            source_location=x.source_location,
        )

    for block in sub.body:
        ops = list[models.Op]()
        for op in block.ops:
            match op:
                case models.Assignment(targets=targets, source=models.ValueTuple(values=sources)):
                    seqd = sequentialize(zip(targets, sources), mktmp=make_temp)
                    for dst, src in seqd:
                        assert isinstance(dst, models.Register)  # TODO: this is bad
                        ops.append(
                            models.Assignment(
                                targets=[dst],
                                source=src,
                                source_location=op.source_location,
                            )
                        )
                case _:
                    ops.append(op)
        block.ops = ops


def sequentialize_parallel_copies(
    _context: CompileContext, contract: models.Contract
) -> models.Contract:
    cloned = deepcopy(contract)
    for subroutine in cloned.all_subroutines():
        logger.debug(f"Sequentializing parallel copies in {subroutine.full_name}")
        _impl(subroutine)
        attrs.validate(subroutine)
    return cloned
