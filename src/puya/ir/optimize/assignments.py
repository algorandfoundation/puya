from puya import log
from puya.context import CompileContext
from puya.errors import InternalError
from puya.ir import models
from puya.ir.visitor_mem_replacer import MemoryReplacer

logger = log.get_logger(__name__)


def copy_propagation(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    set_lookup = dict[models.Register, list[models.Register]]()
    all_equivalence_sets = list[list[models.Register]]()

    modified = False
    for block in subroutine.body:
        for op in block.ops.copy():
            match op:
                case models.Assignment(targets=[target], source=models.Register() as source):
                    try:
                        equiv_set = set_lookup[source]
                        assert source in equiv_set
                    except KeyError:
                        set_lookup[source] = equiv_set = [source]
                        all_equivalence_sets.append(equiv_set)
                    equiv_set.append(target)
                    set_lookup[target] = equiv_set
                    block.ops.remove(op)
                    modified = True

    replacements = dict[models.Register, models.Register]()
    for equivalence_set in all_equivalence_sets:
        assert len(equivalence_set) >= 2
        equiv_set_ids = ", ".join(x.local_id for x in equivalence_set)
        logger.debug(f"Found equivalence set: {equiv_set_ids}")

        parameters = [r for r in equivalence_set if r in subroutine.parameters]
        match parameters:
            case [param]:
                replacement = param
            case []:
                for reg in equivalence_set:
                    if models.TMP_VAR_INDICATOR not in reg.name:
                        replacement = reg
                        break
                else:  # fall back to first register if all are temp
                    replacement = equivalence_set[0]
            case _:
                raise InternalError("multiple parameters in the same equivalence set")
        logger.debug(f"selected {replacement} from equivalence set")
        for r in equivalence_set:
            if r is not replacement:
                replacements[r] = replacement

    for block in subroutine.body:
        for phi in block.phis.copy():
            try:
                (single_register,) = {replacements.get(arg.value, arg.value) for arg in phi.args}
            except ValueError:
                continue
            else:
                # don't replace if phi.register is being used as a replacement for another register
                if phi.register not in replacements.values():
                    replacements[phi.register] = single_register
                    block.phis.remove(phi)
                    modified = True
    replaced = MemoryReplacer.apply(subroutine.body, replacements=replacements)
    if replaced:
        logger.debug(f"Copy propagation made {replaced} modifications")
        modified = True

    return modified
