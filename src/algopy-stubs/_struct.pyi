import typing as t

__all__ = [
    "Struct",
]

@t.dataclass_transform(
    eq_default=False, order_default=False, kw_only_default=False, field_specifiers=()
)
class StructMeta(type):
    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, object],
        *,
        kw_only: bool = False,
        # **kwargs: t.Any,
    ) -> StructMeta: ...

class Struct(metaclass=StructMeta):
    """Base class for struct types"""
