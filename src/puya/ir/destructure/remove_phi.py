from puya import log
from puya.ir import models
from puya.ir.visitor_mem_replacer import MemoryReplacer

logger = log.get_logger(__name__)


def convert_to_cssa(sub: models.Subroutine) -> None:
    logger.debug("Converting to CSSA")
    max_versions = dict[str, int]()
    for reg in sub.get_assigned_registers():
        max_versions[reg.name] = max(max_versions.get(reg.name, 0), reg.version)

    def make_prime(mem: models.Register) -> models.Register:
        max_versions[mem.name] += 1
        return models.Register(
            source_location=mem.source_location,
            ir_type=mem.ir_type,
            name=mem.name,
            version=max_versions[mem.name],
        )

    block_exit_copies = dict[models.BasicBlock, list[tuple[models.Register, models.Register]]]()
    for phi_block in sub.body:
        prime_phis = list[models.Phi]()
        prime_copies = list[tuple[models.Register, models.Register]]()
        for phi in phi_block.phis:
            if not phi.args:
                phi_block.ops.insert(
                    0,
                    models.Assignment(
                        targets=[phi.register],
                        source=models.Undefined(
                            ir_type=phi.ir_type, source_location=phi.source_location
                        ),
                        source_location=phi.source_location,
                    ),
                )
            else:
                prime_args = list[models.PhiArgument]()
                for phi_arg in phi.args:
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
                phi_prime = models.Phi(register=make_prime(phi.register), args=prime_args)
                prime_phis.append(phi_prime)
                prime_copies.append((phi.register, phi_prime.register))
        phi_block.phis = prime_phis
        if prime_copies:
            phi_block.ops.insert(0, _make_copy_assignment(prime_copies))

    for block, copies in block_exit_copies.items():
        block.ops.append(_make_copy_assignment(copies))


def _make_copy_assignment(
    copies: list[tuple[models.Register, models.Register]],
) -> models.Assignment:
    if len(copies) == 1:
        ((dst, src),) = copies
        targets = [dst]
        source: models.ValueProvider = src
    else:
        targets_tup, sources_tup = zip(*copies, strict=True)
        targets = list(targets_tup)
        sources_list = list(sources_tup)
        source = models.ValueTuple(source_location=None, values=sources_list)
    return models.Assignment(
        targets=targets,
        source=source,
        source_location=None,
    )


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
