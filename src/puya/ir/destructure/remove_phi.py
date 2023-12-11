from copy import deepcopy

import structlog.typing

from puya.context import CompileContext
from puya.ir import models
from puya.ir.visitor_mem_replacer import MemoryReplacer

logger: structlog.typing.FilteringBoundLogger = structlog.get_logger(__name__)


def convert_to_cssa(sub: models.Subroutine) -> None:
    max_versions = dict[str, int]()
    for reg in sub.get_assigned_registers():
        max_versions[reg.name] = max(max_versions.get(reg.name, 0), reg.version)

    def make_prime(mem: models.Register) -> models.Register:
        max_versions[mem.name] += 1
        return models.Register(
            source_location=mem.source_location,
            atype=mem.atype,
            name=mem.name,
            version=max_versions[mem.name],
        )

    block_exit_copies = dict[models.BasicBlock, list[tuple[models.Register, models.Register]]]()
    undefined = set[models.Register]()
    for phi_block in sub.body:
        prime_phis = list[models.Phi]()
        prime_copies = list[tuple[models.Register, models.Register]]()
        for phi in phi_block.phis:
            if not phi.args or all(
                phi_arg.value in undefined for phi_arg in phi.args
            ):  # omit undefined
                undefined.add(phi.register)
                continue
            prime_args = list[models.PhiArgument]()
            undefined_predecessors = list[models.BasicBlock]()
            for phi_arg in phi.args:
                if phi_arg.value in undefined:
                    undefined_predecessors.append(phi_arg.through)
                    continue
                prime_arg_reg = make_prime(phi_arg.value)
                prime_arg = models.PhiArgument(
                    value=prime_arg_reg,
                    through=phi_arg.through,
                )
                prime_args.append(prime_arg)
                # insert copy to prime arg at end of predecessor
                block_exit_copies.setdefault(phi_arg.through, []).append(
                    (prime_arg_reg, phi_arg.value)
                )
            phi_prime = models.Phi(
                register=make_prime(phi.register),
                args=prime_args,
                undefined_predecessors=undefined_predecessors,
            )
            prime_phis.append(phi_prime)
            prime_copies.append((phi.register, phi_prime.register))
        phi_block.phis = prime_phis
        if prime_copies:
            phi_block.ops.insert(0, _make_copy_assignment(prime_copies))

    for block, copies in block_exit_copies.items():
        block.ops.append(_make_copy_assignment(copies))


def _make_copy_assignment(
    copies: list[tuple[models.Register, models.Register]]
) -> models.Assignment:
    if len(copies) == 1:
        ((dst, src),) = copies
        targets = [dst]
        source: models.ValueProvider = src
    else:
        targets_tup, sources_tup = zip(*copies, strict=True)
        targets = list(targets_tup)
        sources_list = list(sources_tup)
        # TODO: remove the below reversals, for minimizing diffs
        targets.reverse()
        sources_list.reverse()
        source = models.ValueTuple(source_location=None, values=sources_list)
    return models.Assignment(
        targets=targets,
        source=source,
        source_location=None,
    )


def destructure_cssa(sub: models.Subroutine) -> None:
    # Once the sub is in CSSA, destructuring is trivial.
    # All variables involved in a Phi can be given the same name, and the Phi can be removed.
    for block in sub.body:
        phis = block.phis
        block.phis = []
        for phi in phis:
            MemoryReplacer.apply(
                # We only need to look in the predecessors,
                # since this is where the prime insertions occurred
                blocks=block.predecessors,
                find=(arg.value for arg in phi.args),
                replacement=phi.register,
            )


def convert_contract_to_cssa(
    _context: CompileContext, contract: models.Contract
) -> models.Contract:
    cloned = deepcopy(contract)
    for sub in cloned.all_subroutines():
        convert_to_cssa(sub)
    return cloned


def remove_phi_nodes(_context: CompileContext, contract: models.Contract) -> models.Contract:
    cloned = deepcopy(contract)
    for subroutine in cloned.all_subroutines():
        logger.debug(f"Removing Phis from {subroutine.full_name}")
        subroutine.validate_with_ssa()
        destructure_cssa(subroutine)
    return cloned
