import itertools
from collections import defaultdict
from collections.abc import Callable, Iterator

import attrs

from puya import log
from puya.context import ArtifactCompileContext
from puya.ir import models as ir
from puya.ir.avm_ops import AVMOp
from puya.ir.builder._utils import OpFactory, assign_intrinsic_op
from puya.ir.context import IRRegisterContext
from puya.ir.types_ import ArrayType, IRType, PrimitiveIRType
from puya.ir.visitor import IRTraverser
from puya.ir.visitor_mutator import IRMutator
from puya.parse import SourceLocation
from puya.utils import attrs_extend

logger = log.get_logger(__name__)


@attrs.define(kw_only=True)
class IRArrayBuildContext(ArtifactCompileContext, IRRegisterContext):
    """
    A simplified build context for lowering array nodes within basic blocks.
    As it only needs to introduce temporaries into existing basic blocks don't need to use
    BraunSSA or BlockBuilder
    """

    add_op: Callable[[ir.Op], None]  # type: ignore[assignment]
    _versions: dict[str, int]
    modified: bool = False
    _tmp_counters: defaultdict[str, Iterator[int]] = attrs.field(
        factory=lambda: defaultdict(itertools.count)
    )

    def _next_version(self, name: str) -> int:
        try:
            version = self._versions[name] + 1
        except KeyError:
            version = 1
        self._versions[name] = version
        return version

    def new_register(
        self, name: str, ir_type: IRType, location: SourceLocation | None
    ) -> ir.Register:
        return ir.Register(
            name=name,
            version=self._next_version(name),
            ir_type=ir_type,
            source_location=location,
        )

    def next_tmp_name(self, description: str) -> str:
        counter_value = next(self._tmp_counters[description])
        # array prefix ensure uniqueness with other temps
        return f"array{ir.TMP_VAR_INDICATOR}{description}{ir.TMP_VAR_INDICATOR}{counter_value}"

    def add_assignment(
        self, targets: list[ir.Register], source: ir.ValueProvider, loc: SourceLocation | None
    ) -> None:
        self.add_op(ir.Assignment(targets=targets, source=source, source_location=loc))


def lower_array_nodes(ctx: ArtifactCompileContext, subroutine: ir.Subroutine) -> bool:
    # TODO: combine context + visitor?
    def add_op(op: ir.Op) -> None:
        replacer.current_block_ops.append(op)

    existing_versions = VersionGatherer.gather(subroutine)
    context = attrs_extend(IRArrayBuildContext, ctx, add_op=add_op, versions=existing_versions)
    replacer = ArrayNodeReplacer(context=context)
    for block in subroutine.body:
        replacer.visit_block(block)
    return replacer.modified


@attrs.define
class VersionGatherer(IRTraverser):
    versions: dict[str, int] = attrs.field(factory=dict)

    @classmethod
    def gather(cls, sub: ir.Subroutine) -> dict[str, int]:
        visitor = cls()
        visitor.visit_all_blocks(sub.body)
        return visitor.versions

    def visit_register(self, reg: ir.Register) -> None:
        self.versions[reg.name] = max(self.versions.get(reg.name, 0), reg.version)


@attrs.define(kw_only=True)
class ArrayNodeReplacer(IRMutator):
    context: IRArrayBuildContext
    modified: bool = False

    def visit_array_read_index(self, read: ir.ArrayReadIndex) -> ir.Value:
        self.modified = True
        element_type = _get_element_type(read.array)
        element_size = _get_element_size(element_type)

        factory = OpFactory(self.context, read.source_location)
        bytes_index = factory.mul(read.index, element_size, "bytes_index")
        return self._read_item(read.array, bytes_index, element_type, read.source_location)

    def visit_array_write_index(self, write: ir.ArrayWriteIndex) -> ir.Value:
        self.modified = True
        element_type = _get_element_type(write.array)
        element_size = _get_element_size(element_type)

        factory = OpFactory(self.context, write.source_location)
        bytes_index = factory.mul(write.index, element_size, "bytes_index")
        item_bytes = encode_array_item(
            self.context, write.value, element_type, write.source_location
        )
        return factory.replace(write.array, bytes_index, item_bytes, "updated_array")

    def visit_array_pop(self, pop: ir.ArrayPop) -> ir.ValueTuple:
        self.modified = True
        element_type = _get_element_type(pop.array)
        element_size = _get_element_size(element_type)

        factory = OpFactory(self.context, pop.source_location)
        array_length = factory.len(pop.array, "array_length")
        new_length = factory.sub(array_length, element_size, "new_length")
        array_contents = factory.extract3(
            pop.array,
            0,
            new_length,
            "array_contents",
            return_type=pop.array.ir_type,
        )
        item = self._read_item(pop.array, new_length, element_type, pop.source_location)
        return ir.ValueTuple(values=(array_contents, item), source_location=pop.source_location)

    def visit_array_extend(self, append: ir.ArrayExtend) -> ir.Register:
        self.modified = True
        factory = OpFactory(self.context, append.source_location)
        array_contents = factory.concat(
            append.array,
            append.values,
            "array_contents",
            error_message="max array length exceeded",
            return_type=append.array.ir_type,
        )
        return array_contents

    def visit_array_length(self, length: ir.ArrayLength) -> ir.Register:
        self.modified = True
        bytes_len = assign_intrinsic_op(
            self.context,
            target="bytes_len",
            op=AVMOp.len_,
            args=[length.array],
            source_location=length.source_location,
        )
        element_type = _get_element_type(length.array)
        element_size = _get_element_size(element_type)
        array_len = assign_intrinsic_op(
            self.context,
            target="array_len",
            op=AVMOp.div_floor,
            args=[bytes_len, element_size],
            source_location=length.source_location,
        )
        return array_len

    def _read_item(
        self,
        array: ir.Value,
        bytes_index: ir.Value,
        element_type: IRType,
        loc: SourceLocation | None,
    ) -> ir.Value:
        factory = OpFactory(self.context, loc)
        element_size = _get_element_size(element_type)
        if element_type == PrimitiveIRType.uint64:
            return factory.extract_uint64(array, bytes_index, "value")
        else:
            return factory.extract3(
                array, bytes_index, element_size, "value", return_type=element_type
            )


def _get_element_type(value: ir.Value) -> IRType:
    assert isinstance(value.ir_type, ArrayType), "expected array"
    return value.ir_type.element


def _get_element_size(typ: IRType) -> int:
    assert typ == PrimitiveIRType.uint64, "TODO: other types"
    return 8


def encode_array_item(
    context: IRRegisterContext, item: ir.Value, element_type: IRType, loc: SourceLocation | None
) -> ir.Value:
    factory = OpFactory(context, loc)
    if element_type == PrimitiveIRType.uint64:
        return factory.itob(item, "encoded_item")
    else:
        return item
