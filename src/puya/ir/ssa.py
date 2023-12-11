from collections.abc import Sequence

import attrs
import structlog

from puya.avm_type import AVMType
from puya.errors import InternalError
from puya.ir import models as ir
from puya.ir.visitor_mem_replacer import MemoryReplacer
from puya.parse import SourceLocation

logger: structlog.types.FilteringBoundLogger = structlog.get_logger(__name__)


class BraunSSA:
    """
    Constructs CFG+SSA IR directly from an AST like-structure, without having to go
    through an intermediate non-SSA IR and then compute dominance frontiers etc.

    The primary reference is https://pp.ipd.kit.edu/uploads/publikationen/braun13cc.pdf,
    but also of interest is https://pp.ipd.kit.edu/uploads/publikationen/buchwald16cc.pdf,
    in which the algorithm is converted into a functional programming form,
    and formally verified.
    """

    def __init__(
        self,
        all_blocks: Sequence[ir.BasicBlock],
        live_variables: Sequence[ir.Register],
        active_block: ir.BasicBlock,
    ) -> None:
        self._all_blocks = all_blocks  # note: this is a shared reference with BlocksBuilder
        self._sealed_blocks = set[ir.BasicBlock]()
        self._current_def = dict[str, dict[ir.BasicBlock, ir.Register]]()
        self._incomplete_phis = dict[ir.BasicBlock, list[ir.Phi]]()
        self._variable_versions = dict[str, int]()
        # initialize any live variables at the start of the subroutines, i.e. parameters
        for parameter in live_variables:
            self.write_variable(parameter.name, active_block, parameter)
            self._variable_versions[parameter.name] = 1

    def write_variable(self, variable: str, block: ir.BasicBlock, value: ir.Register) -> None:
        self._current_def.setdefault(variable, {})[block] = value

    def has_write(self, variable: str, block: ir.BasicBlock) -> bool:
        try:
            self._current_def[variable][block]
        except KeyError:
            return False
        else:
            return True

    def read_variable(self, variable: str, atype: AVMType, block: ir.BasicBlock) -> ir.Register:
        try:
            result = self._current_def[variable][block]
        except KeyError:
            result = self._read_variable_recursive(variable, atype, block)
        return result

    def _read_variable_recursive(
        self, variable: str, atype: AVMType, block: ir.BasicBlock
    ) -> ir.Register:
        value: ir.Register
        if not self.is_sealed(block):
            logger.debug(
                f"Looking for '{variable}' in an unsealed block creating an incomplete "
                f"Phi: {block}"
            )
            # incomplete CFG
            phi = self._new_phi(block, variable, atype)
            self._incomplete_phis.setdefault(block, []).append(phi)
            value = phi.register
        elif len(block.predecessors) == 1:
            value = self.read_variable(variable, atype, block.predecessors[0])
        else:
            # break any potential cycles with empty Phi
            phi = self._new_phi(block, variable, atype)
            self.write_variable(variable, block, phi.register)
            value = self._add_phi_operands(phi, block)
        self.write_variable(variable, block, value)
        return value

    def new_register(
        self, name: str, atype: AVMType, location: SourceLocation | None
    ) -> ir.Register:
        version = self._variable_versions.get(name, 0)
        self._variable_versions[name] = version + 1
        return ir.Register(source_location=location, name=name, version=version, atype=atype)

    def is_sealed(self, block: ir.BasicBlock) -> bool:
        return block in self._sealed_blocks

    def verify_complete(self) -> None:
        unsealed = [b for b in self._all_blocks if not self.is_sealed(b)]
        if unsealed:
            raise InternalError(
                f"{len(unsealed)} block/s were not sealed: " + ", ".join(map(str, unsealed))
            )
        incomplete_phis = [p for block_phis in self._incomplete_phis.values() for p in block_phis]
        if incomplete_phis:
            # if we get here, there is a bug in this algorithm itself
            raise InternalError(
                f"{len(incomplete_phis)} phi node/s are incomplete: "
                ", ".join(map(str, incomplete_phis))
            )

    def _new_phi(self, block: ir.BasicBlock, variable: str, atype: AVMType) -> ir.Phi:
        reg = self.new_register(variable, atype, location=None)
        phi = ir.Phi(register=reg)
        block.phis.append(phi)

        logger.debug(
            f"Created Phi assignment: {phi} while trying to resolve '{variable}' in {block}"
        )
        return phi

    def _add_phi_operands(self, phi: ir.Phi, block: ir.BasicBlock) -> ir.Register:
        variable = phi.register.name
        for block_pred in block.predecessors:
            pred_variable = self.read_variable(variable, phi.atype, block_pred)
            phi.args.append(
                ir.PhiArgument(
                    value=pred_variable,
                    through=block_pred,
                )
            )
            # temporary work around for windows default code page not handling φ
            phi_str = str(phi).replace("φ", "Phi")
            logger.debug(f"Added {pred_variable} to Phi node: {phi_str} in {block_pred}")
            attrs.validate(phi)
        trivial_replacements = TrivialPhiRemover.try_remove(phi, self._all_blocks)
        if not trivial_replacements:
            return phi.register
        _, result = trivial_replacements[0]

        variable_def = self._current_def[variable]
        for removed_phi, replacement_memory in trivial_replacements:
            for unsealed_block, incomplete_phis in self._incomplete_phis.items():
                if removed_phi in incomplete_phis:
                    raise InternalError(
                        f"removed an incomplete phi {removed_phi} from block {unsealed_block}!!"
                    )
            if replacement_memory.name != variable:
                raise InternalError(
                    "Tangled phi web created during SSA construction",
                    replacement_memory.source_location,
                )
            if removed_phi.register == result:
                result = replacement_memory
            # ensure replacement is also recorded in variable cache
            replacements = 0
            for block_def, arg in variable_def.items():
                if arg == removed_phi.register:
                    variable_def[block_def] = replacement_memory
                    replacements += 1
            logger.debug(
                f"Replaced trivial Phi node: {removed_phi} ({removed_phi.register})"
                f" with {replacement_memory} in current definition for {replacements} blocks"
            )
        return result

    def seal_block(self, block: ir.BasicBlock) -> None:
        logger.debug(f"Sealing {block}")
        if self.is_sealed(block):
            raise InternalError(f"Cannot seal a block that was already sealed: {block}")

        for predecessor in block.predecessors:
            if not predecessor.terminated:
                raise InternalError(f"All predecessors must be terminated before sealing: {block}")

        phi_list = self._incomplete_phis.pop(block, [])
        for phi in phi_list:
            self._add_phi_operands(phi, block)

        self._sealed_blocks.add(block)


@attrs.define(kw_only=True)
class TrivialPhiRemover(MemoryReplacer):
    phi: ir.Phi
    collected: list[ir.Phi] = attrs.field(factory=list)

    @classmethod
    def try_remove(
        cls, phi: ir.Phi, blocks: Sequence[ir.BasicBlock]
    ) -> list[tuple[ir.Phi, ir.Register]]:
        try:
            replacement, *other = {a.value for a in phi.non_self_args}
        except ValueError:
            # # per https://pp.ipd.kit.edu/uploads/publikationen/buchwald16cc.pdf, section 4.1
            logger.warning(f"Variable {phi.register.name} potentially used before assignment")
            return []

        result = []
        # if other, then phi merges >1 value: not trivial
        if not other:
            result.append((phi, replacement))
            # replace users of phi with replacement
            logger.debug(f"Replacing trivial Phi node: {phi} ({phi.register}) with {replacement}")
            # this approach is not very efficient, but is simpler than tracking all usages
            # and good enough for now
            replacer = cls(
                phi=phi,
                find=frozenset([phi.register]),
                replacement=replacement,
            )
            for block in blocks:
                replacer.visit_block(block)
            # recursively check/replace all phi users, which may now be trivial
            for phi_user in replacer.collected:
                result.extend(cls.try_remove(phi_user, blocks))
        return result

    def visit_phi(self, phi: ir.Phi) -> ir.Phi | None:
        if phi is self.phi:
            logger.debug(f"Deleting Phi assignment: {phi}")
            return None
        prior_replace_count = self.replaced
        result = super().visit_phi(phi)
        assert result is phi, "phi instance changed"
        if self.replaced > prior_replace_count:
            self.collected.append(result)
        return result
