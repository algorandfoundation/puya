from puya.awst import wtypes
from puya.awst.visitors import WTypeVisitor
from puya.parse import SourceLocation


class WTypeSourceLocationVisitor(WTypeVisitor[SourceLocation | None]):
    def visit_basic_type(self, _wtype: wtypes.WType) -> SourceLocation | None:
        return None

    def visit_enumeration_type(self, _wtype: wtypes.WEnumeration) -> SourceLocation | None:
        return None

    def visit_bytes_type(self, _wtype: wtypes.BytesWType) -> SourceLocation | None:
        return None

    def visit_group_transaction_type(
        self, _wtype: wtypes.WGroupTransaction
    ) -> SourceLocation | None:
        return None

    def visit_inner_transaction_type(
        self, _wtype: wtypes.WInnerTransaction
    ) -> SourceLocation | None:
        return None

    def visit_inner_transaction_fields_type(
        self, _wtype: wtypes.WInnerTransactionFields
    ) -> SourceLocation | None:
        return None

    def visit_stack_array(self, wtype: wtypes.StackArray) -> SourceLocation | None:
        return wtype.source_location

    def visit_reference_array(self, wtype: wtypes.ReferenceArray) -> SourceLocation | None:
        return wtype.source_location

    def visit_tuple_type(self, wtype: wtypes.WTuple) -> SourceLocation | None:
        return wtype.source_location

    def visit_basic_arc4_type(self, _wtype: wtypes.ARC4Type) -> SourceLocation | None:
        return None

    def visit_arc4_uint(self, wtype: wtypes.ARC4UIntN) -> SourceLocation | None:
        return wtype.source_location

    def visit_arc4_ufixed(self, wtype: wtypes.ARC4UFixedNxM) -> SourceLocation | None:
        return wtype.source_location

    def visit_arc4_tuple(self, wtype: wtypes.ARC4Tuple) -> SourceLocation | None:
        return wtype.source_location

    def visit_arc4_dynamic_array(self, wtype: wtypes.ARC4DynamicArray) -> SourceLocation | None:
        return wtype.source_location

    def visit_arc4_static_array(self, wtype: wtypes.ARC4StaticArray) -> SourceLocation | None:
        return wtype.source_location

    def visit_arc4_struct(self, wtype: wtypes.ARC4Struct) -> SourceLocation | None:
        return wtype.source_location
