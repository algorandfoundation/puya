import enum
import typing
from collections.abc import Mapping, Sequence

from puya.avm import OnCompletionAction, TransactionType
from puya.awst.nodes import UInt64Constant
from puya.errors import CodeError
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb.interface import InstanceBuilder, NodeBuilder, TypeBuilder
from puyapy.awst_build.eb.uint64 import UInt64ExpressionBuilder


class _UInt64EnumTypeBuilder(TypeBuilder):
    enum_type: typing.ClassVar[pytypes.UInt64EnumType]
    enum_data: typing.ClassVar[Mapping[str, enum.IntEnum] | Mapping[str, int]]

    def __init_subclass__(
        cls,
        enum_type: pytypes.UInt64EnumType,
        enum_data: Mapping[str, enum.IntEnum] | Mapping[str, int],
        **kwargs: typing.Any,
    ):
        super().__init_subclass__(**kwargs)
        cls.enum_type = enum_type
        cls.enum_data = enum_data

    def __init__(self, location: SourceLocation):
        super().__init__(self.enum_type, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise CodeError("cannot instantiate enumeration type", location)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        if (data := self.enum_data.get(name)) is None:
            return super().member_access(name, location)
        if isinstance(data, enum.IntEnum):
            teal_alias = data.name
            value = data.value
        else:
            teal_alias = None
            value = data

        const_expr = UInt64Constant(value=value, teal_alias=teal_alias, source_location=location)
        return UInt64ExpressionBuilder(const_expr, self.enum_type)


class OnCompletionActionTypeBuilder(
    _UInt64EnumTypeBuilder,
    enum_type=pytypes.OnCompleteActionType,
    enum_data={oca.name: oca for oca in OnCompletionAction},
):
    pass


class TransactionTypeTypeBuilder(
    _UInt64EnumTypeBuilder,
    enum_type=pytypes.TransactionTypeType,
    enum_data={
        "Payment": TransactionType.pay,
        "KeyRegistration": TransactionType.keyreg,
        "AssetConfig": TransactionType.acfg,
        "AssetTransfer": TransactionType.axfer,
        "AssetFreeze": TransactionType.afrz,
        "ApplicationCall": TransactionType.appl,
    },
):
    pass


class OpUpFeeSourceTypeBuilder(
    _UInt64EnumTypeBuilder,
    enum_type=pytypes.OpUpFeeSourceType,
    enum_data={
        "GroupCredit": 0,
        "AppAccount": 1,
        "Any": 2,
    },
):
    pass
