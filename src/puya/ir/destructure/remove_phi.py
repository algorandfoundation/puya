from collections import defaultdict

from puya import log
from puya.ir import models
from puya.ir.visitor_mem_replacer import MemoryReplacer

logger = log.get_logger(__name__)

_CopyList = list[tuple[models.Register, models.Register]]


def convert_to_cssa(sub: models.Subroutine) -> None:
    logger.debug("Converting to CSSA")
    max_versions = dict[str, int]()
    for reg in sub.get_assigned_registers():
        max_versions[reg.name] = max(max_versions.get(reg.name, 0), reg.version)

    def make_prime(mem: models.Register) -> models.Register:
        max_versions[mem.name] += 1
        return models.Register(
            name=mem.name,
            version=max_versions[mem.name],
            ir_type=mem.ir_type,
            source_location=mem.source_location,
        )

    block_exit_copies = defaultdict[models.BasicBlock, _CopyList](list)
    for phi_block in sub.body:
        keep_phis = []
        for phi in phi_block.phis:
            if not phi.args:
                loc = phi.source_location
                undef_value = models.Undefined(ir_type=phi.ir_type, source_location=loc)
                undef_assignment = models.Assignment(
                    targets=[phi.register], source=undef_value, source_location=loc
                )
                phi_block.ops.insert(0, undef_assignment)
            else:
                for phi_arg in phi.args:
                    reg = phi_arg.value
                    phi_arg.value = make_prime(reg)
                    # insert copy to prime arg at end of predecessor
                    block_exit_copies[phi_arg.through].append((phi_arg.value, reg))
                keep_phis.append(phi)
        phi_block.phis = keep_phis

    for block, copies in block_exit_copies.items():
        block.ops.append(_make_copy_assignment(copies))


def _make_copy_assignment(copies: _CopyList) -> models.Assignment:
    if len(copies) == 1:
        ((dst, src),) = copies
        targets = [dst]
        source: models.ValueProvider = src
    else:
        target_tup, source_values = zip(*copies, strict=True)
        targets = list(target_tup)
        source = models.ValueTuple(source_location=None, values=source_values)
    return models.Assignment(targets=targets, source=source, source_location=None)


def destructure_cssa(sub: models.Subroutine) -> None:
    logger.debug("Removing Phi nodes")
    # Once the sub is in CSSA, destructuring is trivial.
    # All variables involved in a Phi can be given the same name, and the Phi can be removed.
    replacements = dict[models.Register, models.Register]()
    for block in sub.body:
        phis = block.phis
        block.phis = []
        replacements.update({arg.value: phi.register for phi in phis for arg in phi.args})
    MemoryReplacer.apply(sub.body, replacements=replacements)
