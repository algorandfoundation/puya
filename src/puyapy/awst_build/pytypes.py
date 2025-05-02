from __future__ import annotations

import abc
import typing
from collections.abc import Callable, Mapping, Sequence
from functools import cached_property

import attrs
import typing_extensions
from immutabledict import immutabledict

from puya import log
from puya.avm import TransactionType
from puya.awst import wtypes
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation
from puya.program_refs import ContractReference
from puya.utils import lazy_setdefault, unique
from puyapy.awst_build import constants

if typing.TYPE_CHECKING:
    from puyapy.awst_build.intrinsic_models import (
        OpMappingWithOverloads,
        PropertyOpMapping,
    )
    from puyapy.models import ArgKind

logger = log.get_logger(__name__)


ErrorMessage = typing.NewType("ErrorMessage", str)


@attrs.frozen(kw_only=True, str=False, order=False)
class PyType(abc.ABC):
    name: str
    """The canonical fully qualified type name"""
    generic: PyType | None = None
    """The generic type that this type was parameterised from, if any."""
    bases: tuple[PyType, ...] = attrs.field(default=(), converter=tuple["PyType", ...])
    """Direct base classes. probably excluding the implicit builtins.object?"""
    mro: tuple[PyType, ...] = attrs.field(default=(), converter=tuple["PyType", ...])
    """All base cases, in Method Resolution Order"""

    @bases.validator
    def _bases_validate(self, _attribute: object, bases: tuple[PyType, ...]) -> None:
        if len(set(bases)) != len(bases):
            raise InternalError(f"Duplicate bases in {self}: [{', '.join(map(str, bases))}]")

    @mro.validator
    def _mro_validate(self, _attribute: object, mro: tuple[PyType, ...]) -> None:
        bases_missing_from_mro = set(self.bases).difference(mro)
        if bases_missing_from_mro:
            raise InternalError(
                f"Bases missing from MRO in {self}:"
                f" [{', '.join(map(str, bases_missing_from_mro))}]"
            )

    @cached_property
    def _friendly_name(self) -> str:
        """User-friendly fully-qualified name.

        Basically just strips "builtins." from types, and removes the private part
        of algopy names.
        """
        import re

        result, _ = re.subn(r"\bbuiltins\.", "", self.name)
        result, _ = re.subn(r"algopy\._[^.]+", "algopy", result)
        result = result.replace(NoneType.name, "None")
        return result

    def __str__(self) -> str:
        return self._friendly_name

    @property
    @abc.abstractmethod
    def wtype(self) -> wtypes.WType | ErrorMessage:
        """The WType that this type represents, if any."""

    def checked_wtype(self, location: SourceLocation | None) -> wtypes.WType:
        match self.wtype:
            case wtypes.WType() as wtype:
                return wtype
            case str(msg):
                raise CodeError(msg, location)
            case _:
                typing.assert_never(self.wtype)

    def parameterise(
        self,
        args: Sequence[PyType],  # noqa: ARG002
        source_location: SourceLocation | None,
    ) -> PyType:
        """Produce parameterised type.
        Throws if not a generic type of if a parameterised generic type."""
        if self.generic:
            raise CodeError(f"type already has parameters: {self}", source_location)
        raise CodeError(f"not a generic type: {self}", source_location)

    @typing.final
    def __lt__(self, other: object) -> bool:
        if not isinstance(other, PyType):
            return NotImplemented
        # self < other -> self is a supertype of other
        return self in other.mro

    @typing.final
    def __le__(self, other: object) -> bool:
        if not isinstance(other, PyType):
            return NotImplemented
        return self == other or self < other

    @typing.final
    def __gt__(self, other: object) -> bool:
        if not isinstance(other, PyType):
            return NotImplemented
        raise TypeError("types are partial ordered")

    @typing.final
    def __ge__(self, other: object) -> bool:
        if not isinstance(other, PyType):
            return NotImplemented
        raise TypeError("types are partial ordered")

    def is_type_or_subtype(self, *of_any: PyType) -> bool:
        return any(of <= self for of in of_any)

    def is_type_or_supertype(self, *of_any: PyType) -> bool:
        return any(self <= of for of in of_any)


class RuntimeType(PyType, abc.ABC):
    @typing.override
    @property
    @abc.abstractmethod
    def wtype(self) -> wtypes.WType: ...


_builtins_registry: typing.Final = dict[str, PyType]()


_TPyType = typing_extensions.TypeVar("_TPyType", bound=PyType, default=PyType)


def _register_builtin(typ: _TPyType, *, alias: str | None = None) -> _TPyType:
    name = alias or typ.name
    existing_entry = _builtins_registry.get(name)
    if existing_entry is None:
        _builtins_registry[name] = typ
    elif existing_entry is typ:
        logger.debug(f"Duplicate registration of {typ}")
    else:
        raise InternalError(f"Duplicate mapping of {name}")
    return typ


def builtins_registry() -> dict[str, PyType]:
    """Get a copy of the builtins registry"""
    return _builtins_registry.copy()


# https://typing.readthedocs.io/en/latest/spec/literal.html#legal-and-illegal-parameterizations
# We don't support enums as typing.Literal parameters. mypy encodes these as str values with
# an additional "fallback" data member, but we don't need that complication.
# mypy.types.LiteralValue also includes float, noting its invalid as a parameterization, but
# we exclude this here.
# None types are also encoded as their own type, but we have them as values here.
TypingLiteralValue: typing.TypeAlias = int | bytes | str | bool | None
_TypeArgs: typing.TypeAlias = tuple[PyType, ...]
_Parameterise = typing_extensions.TypeAliasType(
    "_Parameterise",
    Callable[["_GenericType[_TPyType]", _TypeArgs, SourceLocation | None], _TPyType],
    type_params=(_TPyType,),
)


@typing.final
@attrs.frozen(order=False)
class _GenericType(PyType, abc.ABC, typing.Generic[_TPyType]):
    """Represents a typing.Generic type with unknown parameters"""

    _parameterise: _Parameterise[_TPyType]
    _instance_cache: dict[_TypeArgs, _TPyType] = attrs.field(factory=dict, eq=False)

    def __attrs_post_init__(self) -> None:
        _register_builtin(self)

    @typing.override
    @property
    def wtype(self) -> ErrorMessage:
        return ErrorMessage("generic type usage requires parameters")

    @typing.override
    def parameterise(
        self, args: Sequence[PyType], source_location: SourceLocation | None
    ) -> _TPyType:
        return lazy_setdefault(
            self._instance_cache,
            key=tuple(args),
            default=lambda args_: self._parameterise(self, args_, source_location),
        )


def _parameterise_type_type(
    self: _GenericType,  # noqa: ARG001
    args: _TypeArgs,
    source_location: SourceLocation | None,
) -> TypeType:
    try:
        (arg,) = args
    except ValueError:
        raise CodeError(
            f"expected a single type parameter, got {len(args)} parameters", source_location
        ) from None
    return TypeType(typ=arg)


GenericTypeType: typing.Final[PyType] = _GenericType(
    name="builtins.type",
    parameterise=_parameterise_type_type,
)


@typing.final
@attrs.frozen(order=False)
class TypeType(PyType):
    typ: PyType
    generic: PyType = attrs.field(default=GenericTypeType, init=False)
    name: str = attrs.field(init=False)

    @name.default
    def _name_default(self) -> str:
        return f"{self.generic.name}[{self.typ.name}]"

    @typing.override
    @property
    def wtype(self) -> ErrorMessage:
        return ErrorMessage("type objects are not usable as values")


@typing.final
@attrs.frozen(order=False)
class TypingLiteralType(PyType):
    value: TypingLiteralValue
    source_location: SourceLocation | None = attrs.field(eq=False)
    name: str = attrs.field(init=False)
    generic: None = attrs.field(default=None, init=False)
    bases: tuple[PyType, ...] = attrs.field(default=(), init=False)
    mro: tuple[PyType, ...] = attrs.field(default=(), init=False)

    @name.default
    def _name_default(self) -> str:
        return f"typing.Literal[{self.value!r}]"

    @typing.override
    @property
    def wtype(self) -> ErrorMessage:
        return ErrorMessage(f"{self} is not usable as a value")


def _flatten_nested_unions(types: Sequence[PyType]) -> tuple[PyType, ...]:
    result = list[PyType]()
    for t in types:
        if isinstance(t, UnionType):
            result.extend(t.types)
        else:
            result.append(t)
    return tuple(unique(result))


@typing.final
@attrs.frozen(order=False)
class UnionType(PyType):
    types: tuple[PyType, ...] = attrs.field(
        converter=_flatten_nested_unions, validator=attrs.validators.min_len(2)
    )
    name: str = attrs.field(init=False)
    generic: None = attrs.field(default=None, init=False)
    bases: tuple[PyType, ...] = attrs.field(default=(), init=False)
    mro: tuple[PyType, ...] = attrs.field(default=(), init=False)
    source_location: SourceLocation = attrs.field(eq=False)

    @name.default
    def _name(self) -> str:
        return " | ".join(t.name for t in self.types)

    @typing.override
    @property
    def wtype(self) -> ErrorMessage:
        return ErrorMessage("type unions are unsupported at this location")


@attrs.frozen(order=False)
class _BaseType(PyType):
    """Type that is only usable as a base type"""

    @typing.override
    @property
    def wtype(self) -> ErrorMessage:
        return ErrorMessage(f"{self} is only usable as a base type")

    def __attrs_post_init__(self) -> None:
        _register_builtin(self)


@attrs.frozen(kw_only=True, order=False)
class TupleLikeType(PyType, abc.ABC):
    items: tuple[PyType, ...]
    source_location: SourceLocation | None = attrs.field(eq=False)


def _parameterise_tuple(
    self: _GenericType[TupleType], args: _TypeArgs, source_location: SourceLocation | None
) -> TupleType:
    name = f"{self.name}[{', '.join(pyt.name for pyt in args)}]"
    return TupleType(name=name, items=tuple(args), source_location=source_location)


GenericTupleType: typing.Final = _GenericType(
    name="builtins.tuple",
    parameterise=_parameterise_tuple,
)


@attrs.frozen(kw_only=True, order=False)
class TupleType(TupleLikeType):
    generic: PyType | None = attrs.field(default=GenericTupleType, init=False)
    bases: tuple[PyType, ...] = attrs.field(default=(), init=False)
    mro: tuple[PyType, ...] = attrs.field(default=(), init=False)

    @property
    def wtype(self) -> wtypes.WTuple | ErrorMessage:
        item_wtypes = []
        for i in self.items:
            match i.wtype:
                case wtypes.WType() as wtype:
                    item_wtypes.append(wtype)
                case str(err):
                    return err
                case other:
                    typing.assert_never(other)
        return wtypes.WTuple(
            types=item_wtypes,
            source_location=self.source_location,
        )


NamedTupleBaseType: typing.Final[PyType] = _BaseType(name="typing.NamedTuple")


@attrs.frozen(kw_only=True, order=False)
class NamedTupleType(TupleType, RuntimeType):
    fields: immutabledict[str, PyType] = attrs.field(converter=immutabledict)
    items: tuple[PyType, ...] = attrs.field(init=False)
    generic: None = attrs.field(default=None, init=False)
    bases: tuple[PyType, ...] = attrs.field(default=(NamedTupleBaseType,), init=False)
    mro: tuple[PyType, ...] = attrs.field(default=(NamedTupleBaseType,), init=False)
    desc: str | None = None
    wtype: wtypes.WTuple = attrs.field(init=False)

    @items.default
    def _items(self) -> tuple[PyType, ...]:
        return tuple(self.fields.values())

    @wtype.default
    def _wtype(self) -> wtypes.WTuple:
        unnamed_type = super().wtype
        if isinstance(unnamed_type, str):
            raise CodeError(unnamed_type, self.source_location)
        return attrs.evolve(
            unnamed_type,
            name=self.name,
            names=tuple(self.fields),
            source_location=self.source_location,
            desc=self.desc,
        )


@attrs.frozen(order=False)
class SequenceType(PyType, abc.ABC):
    items: PyType


@typing.final
@attrs.frozen(order=False)
class ArrayType(SequenceType, RuntimeType):
    size: int | None
    wtype: wtypes.WType
    # convenience accessors
    items_wtype: wtypes.WType
    source_location: SourceLocation | None = attrs.field(eq=False)


@typing.final
@attrs.frozen(order=False)
class StorageProxyType(RuntimeType):
    content: PyType
    wtype: wtypes.WType
    # convenience accessors
    content_wtype: wtypes.WType


@typing.final
@attrs.frozen(order=False)
class StorageMapProxyType(RuntimeType):
    generic: PyType
    key: PyType
    content: PyType
    wtype: wtypes.WType
    # convenience accessors
    key_wtype: wtypes.WType
    content_wtype: wtypes.WType


@typing.final
@attrs.frozen
class FuncArg:
    type: PyType
    name: str | None
    kind: ArgKind


@typing.final
@attrs.frozen(kw_only=True, order=False)
class FuncType(PyType):
    ret_type: PyType
    args: tuple[FuncArg, ...] = attrs.field(converter=tuple[FuncArg, ...])
    # static data
    generic: None = None
    bases: tuple[PyType, ...] = attrs.field(default=(), init=False)
    mro: tuple[PyType, ...] = attrs.field(default=(), init=False)

    @typing.override
    @property
    def wtype(self) -> ErrorMessage:
        return ErrorMessage("function objects are not usable as values")


@typing.final
@attrs.frozen(order=False)
class StaticType(PyType):
    @typing.override
    @property
    def wtype(self) -> ErrorMessage:
        return ErrorMessage(f"{self} is only usable as a type and cannot be instantiated")


@typing.final
@attrs.frozen(kw_only=True, order=False)
class ContractType(PyType):
    generic: None = attrs.field(default=None, init=False)
    module_name: str
    class_name: str
    name: ContractReference = attrs.field(init=False)
    source_location: SourceLocation = attrs.field(eq=False)

    @name.default
    def _name(self) -> ContractReference:
        return ContractReference(".".join((self.module_name, self.class_name)))

    @typing.override
    @property
    def wtype(self) -> ErrorMessage:
        return ErrorMessage(f"{self} is only usable as a type and cannot be instantiated")


ObjectType: typing.Final[PyType] = _register_builtin(StaticType(name="builtins.object"))


@typing.final
@attrs.frozen(init=False, order=False)
class StructType(RuntimeType):
    fields: immutabledict[str, PyType] = attrs.field(
        converter=immutabledict, validator=[attrs.validators.min_len(1)]
    )
    frozen: bool
    wtype: wtypes.ARC4Struct | wtypes.WStructType
    source_location: SourceLocation | None = attrs.field(eq=False)
    generic: None = None
    desc: str | None = None

    @cached_property
    def names(self) -> tuple[str, ...]:
        return tuple(self.fields.keys())

    @cached_property
    def types(self) -> tuple[PyType, ...]:
        return tuple(self.fields.values())

    def __init__(
        self,
        *,
        base: PyType,
        name: str,
        desc: str | None,
        fields: Mapping[str, PyType],
        frozen: bool,
        source_location: SourceLocation | None,
    ):
        field_wtypes = {
            name: field_typ.checked_wtype(source_location) for name, field_typ in fields.items()
        }  # TODO: this is a bit of a kludge
        wtype_cls: type[wtypes.ARC4Struct | wtypes.WStructType]
        if base is ARC4StructBaseType:
            wtype_cls = wtypes.ARC4Struct
        elif base is StructBaseType:
            wtype_cls = wtypes.WStructType
        else:
            raise InternalError(f"Unknown struct base type: {base}", source_location)
        wtype = wtype_cls(
            fields=field_wtypes,
            name=name,
            desc=desc,
            frozen=frozen,
            source_location=source_location,
        )
        self.__attrs_init__(
            bases=[base],
            mro=[base],
            name=name,
            desc=desc,
            wtype=wtype,
            fields=fields,
            frozen=frozen,
            source_location=source_location,
        )


@typing.final
@attrs.frozen(order=False)
class _SimpleType(RuntimeType):
    wtype: wtypes.WType

    def __attrs_post_init__(self) -> None:
        _register_builtin(self)


@typing.final
@attrs.frozen(order=False)
class LiteralOnlyType(PyType):
    python_type: type[int | bytes | str]
    name: str = attrs.field(init=False)

    @name.default
    def _name(self) -> str:
        return ".".join((self.python_type.__module__, self.python_type.__qualname__))

    @typing.override
    @property
    def wtype(self) -> ErrorMessage:
        return ErrorMessage(f"Python literals of type {self} cannot be used as runtime values")


NoneType: typing.Final[RuntimeType] = _SimpleType(name="types.NoneType", wtype=wtypes.void_wtype)
NeverType: typing.Final[PyType] = _SimpleType(name="typing.Never", wtype=wtypes.void_wtype)
IntLiteralType: typing.Final = _register_builtin(LiteralOnlyType(int))
StrLiteralType: typing.Final = _register_builtin(LiteralOnlyType(str))
BytesLiteralType: typing.Final = _register_builtin(LiteralOnlyType(bytes))
BoolType: typing.Final[RuntimeType] = _SimpleType(
    name="builtins.bool",
    wtype=wtypes.bool_wtype,
    bases=[IntLiteralType],
    mro=[IntLiteralType],
)

UInt64Type: typing.Final[RuntimeType] = _SimpleType(
    name="algopy._primitives.UInt64",
    wtype=wtypes.uint64_wtype,
)
BigUIntType: typing.Final[RuntimeType] = _SimpleType(
    name="algopy._primitives.BigUInt",
    wtype=wtypes.biguint_wtype,
)
BytesType: typing.Final[RuntimeType] = _SimpleType(
    name="algopy._primitives.Bytes",
    wtype=wtypes.bytes_wtype,
)
StringType: typing.Final[RuntimeType] = _SimpleType(
    name="algopy._primitives.String",
    wtype=wtypes.string_wtype,
)
AccountType: typing.Final[RuntimeType] = _SimpleType(
    name="algopy._reference.Account",
    wtype=wtypes.account_wtype,
)
AssetType: typing.Final[RuntimeType] = _SimpleType(
    name="algopy._reference.Asset",
    wtype=wtypes.asset_wtype,
)
ApplicationType: typing.Final[RuntimeType] = _SimpleType(
    name="algopy._reference.Application",
    wtype=wtypes.application_wtype,
)


@attrs.frozen(init=False, order=False)
class UInt64EnumType(RuntimeType):
    def __init__(self, name: str):
        self.__attrs_init__(
            name=name,
            bases=[UInt64Type],
            mro=[UInt64Type],
        )
        _register_builtin(self)

    @property
    def wtype(self) -> wtypes.WType:
        return wtypes.uint64_wtype


OnCompleteActionType: typing.Final = UInt64EnumType(
    name="algopy._constants.OnCompleteAction",
)
TransactionTypeType: typing.Final = UInt64EnumType(
    name="algopy._constants.TransactionType",
)
OpUpFeeSourceType: typing.Final = UInt64EnumType(
    name="algopy._util.OpUpFeeSource",
)

ARC4StringType: typing.Final[RuntimeType] = _SimpleType(
    name="algopy.arc4.String",
    wtype=wtypes.arc4_string_alias,
)
ARC4BoolType: typing.Final[RuntimeType] = _SimpleType(
    name="algopy.arc4.Bool",
    wtype=wtypes.arc4_bool_wtype,
)


@attrs.frozen(order=False)
class ARC4UIntNType(RuntimeType):
    bits: int
    wtype: wtypes.ARC4UIntN
    native_type: RuntimeType


def _require_int_literal(
    generic: _GenericType[_TPyType],
    type_arg: PyType,
    source_location: SourceLocation | None,
    *,
    position_qualifier: str = "",
) -> int:
    match type_arg:
        case TypingLiteralType(value=int(value)):
            return value
    if position_qualifier:
        position_qualifier = position_qualifier + " "
    raise CodeError(
        f"{generic} expects a typing.Literal[<int>] as a {position_qualifier}parameter",
        source_location,
    )


def _make_arc4_unsigned_int_parameterise(
    *, native_type: RuntimeType, max_bits: int | None = None
) -> _Parameterise:
    def parameterise(
        self: _GenericType, args: _TypeArgs, source_location: SourceLocation | None
    ) -> ARC4UIntNType:
        try:
            (bits_t,) = args
        except ValueError:
            raise CodeError(
                f"expected a single type parameter, got {len(args)} parameters", source_location
            ) from None
        bits = _require_int_literal(self, bits_t, source_location)
        if (max_bits is not None) and bits > max_bits:
            raise CodeError(f"max bit size of {self} is {max_bits}, got {bits}", source_location)

        name = f"{self.name}[{bits_t.name}]"
        return ARC4UIntNType(
            generic=self,
            name=name,
            bits=bits,
            native_type=native_type,
            wtype=wtypes.ARC4UIntN(n=bits, source_location=source_location),
        )

    return parameterise


GenericARC4UIntNType: typing.Final = _GenericType(
    name="algopy.arc4.UIntN",
    parameterise=_make_arc4_unsigned_int_parameterise(native_type=UInt64Type, max_bits=64),
)
GenericARC4BigUIntNType: typing.Final = _GenericType(
    name="algopy.arc4.BigUIntN",
    parameterise=_make_arc4_unsigned_int_parameterise(native_type=BigUIntType),
)


ARC4UIntN_Aliases: typing.Final = immutabledict[int, ARC4UIntNType](
    {
        (_bits := 2**_exp): _register_builtin(
            (GenericARC4UIntNType if _bits <= 64 else GenericARC4BigUIntNType).parameterise(
                [TypingLiteralType(value=_bits, source_location=None)], source_location=None
            ),
            alias=f"algopy.arc4.UInt{_bits}",
        )
        for _exp in range(3, 10)
    }
)
ARC4ByteType: typing.Final = _register_builtin(
    ARC4UIntNType(
        generic=None,
        name="algopy.arc4.Byte",
        wtype=wtypes.arc4_byte_alias,
        bits=8,
        bases=[ARC4UIntN_Aliases[8]],
        mro=[ARC4UIntN_Aliases[8]],
        native_type=UInt64Type,
    )
)


@attrs.frozen(order=False)
class ARC4UFixedNxMType(RuntimeType):
    generic: _GenericType
    bits: int
    precision: int
    wtype: wtypes.WType


def _make_arc4_unsigned_fixed_parameterise(*, max_bits: int | None = None) -> _Parameterise:
    def parameterise(
        self: _GenericType, args: _TypeArgs, source_location: SourceLocation | None
    ) -> ARC4UFixedNxMType:
        try:
            bits_t, precision_t = args
        except ValueError:
            raise CodeError(
                f"expected two type parameters, got {len(args)} parameters", source_location
            ) from None
        bits = _require_int_literal(self, bits_t, source_location, position_qualifier="first")
        precision = _require_int_literal(
            self, precision_t, source_location, position_qualifier="second"
        )
        if (max_bits is not None) and bits > max_bits:
            raise CodeError(f"max bit size of {self} is {max_bits}, got {bits}", source_location)

        name = f"{self.name}[{bits_t.name}, {precision_t.name}]"
        return ARC4UFixedNxMType(
            generic=self,
            name=name,
            bits=bits,
            precision=precision,
            wtype=wtypes.ARC4UFixedNxM(n=bits, m=precision, source_location=source_location),
        )

    return parameterise


GenericARC4UFixedNxMType: typing.Final = _GenericType(
    name="algopy.arc4.UFixedNxM",
    parameterise=_make_arc4_unsigned_fixed_parameterise(max_bits=64),
)
GenericARC4BigUFixedNxMType: typing.Final = _GenericType(
    name="algopy.arc4.BigUFixedNxM",
    parameterise=_make_arc4_unsigned_fixed_parameterise(),
)


def _parameterise_arc4_tuple(
    self: _GenericType[ARC4TupleType],  # noqa: ARG001
    args: _TypeArgs,
    source_location: SourceLocation | None,
) -> ARC4TupleType:
    item_wtypes = tuple(arg.checked_wtype(source_location) for arg in args)
    wtype = wtypes.ARC4Tuple(types=item_wtypes, source_location=source_location)
    return ARC4TupleType(items=tuple(args), wtype=wtype, source_location=source_location)


GenericARC4TupleType: typing.Final = _GenericType(
    name="algopy.arc4.Tuple",
    parameterise=_parameterise_arc4_tuple,
)


@typing.final
@attrs.frozen(kw_only=True, order=False)
class ARC4TupleType(TupleLikeType, RuntimeType):
    generic: _GenericType = attrs.field(default=GenericARC4TupleType, init=False)
    name: str = attrs.field(init=False)
    bases: tuple[PyType, ...] = attrs.field(default=(), init=False)
    mro: tuple[PyType, ...] = attrs.field(default=(), init=False)
    wtype: wtypes.ARC4Tuple

    @name.default
    def _name(self) -> str:
        return f"{self.generic.name}[{', '.join(pyt.name for pyt in self.items)}]"


CompiledContractType: typing.Final = _register_builtin(
    NamedTupleType(
        name="algopy._compiled.CompiledContract",
        fields={
            "approval_program": GenericTupleType.parameterise([BytesType, BytesType], None),
            "clear_state_program": GenericTupleType.parameterise([BytesType, BytesType], None),
            "extra_program_pages": UInt64Type,
            "global_uints": UInt64Type,
            "global_bytes": UInt64Type,
            "local_uints": UInt64Type,
            "local_bytes": UInt64Type,
        },
        source_location=None,
    )
)
CompiledLogicSigType: typing.Final = _register_builtin(
    NamedTupleType(
        name="algopy._compiled.CompiledLogicSig",
        fields={
            "account": AccountType,
        },
        source_location=None,
    )
)


@typing.final
@attrs.frozen(order=False)
class VariadicTupleType(SequenceType):
    items: PyType
    generic: _GenericType = attrs.field(default=GenericTupleType, init=False)
    bases: tuple[PyType, ...] = attrs.field(default=(), init=False)
    mro: tuple[PyType, ...] = attrs.field(default=(), init=False)
    name: str = attrs.field(init=False)

    @name.default
    def _name_factory(self) -> str:
        return f"{self.generic.name}[{self.items.name}, ...]"

    @typing.override
    @property
    def wtype(self) -> ErrorMessage:
        return ErrorMessage("variadic tuples cannot be used as runtime values")


def _make_array_parameterise(
    typ: type[wtypes.StackArray | wtypes.ReferenceArray | wtypes.ARC4DynamicArray],
) -> _Parameterise[ArrayType]:
    def parameterise(
        self: _GenericType[ArrayType], args: _TypeArgs, source_location: SourceLocation | None
    ) -> ArrayType:
        try:
            (arg,) = args
        except ValueError:
            raise CodeError(
                f"expected a single type parameter, got {len(args)} parameters", source_location
            ) from None
        name = f"{self.name}[{arg.name}]"
        items_wtype = arg.checked_wtype(source_location)

        return ArrayType(
            generic=self,
            name=name,
            size=None,
            items=arg,
            wtype=typ(element_type=items_wtype, source_location=source_location),
            items_wtype=items_wtype,
            source_location=source_location,
        )

    return parameterise


GenericArrayType: typing.Final = _GenericType(
    name="algopy._array.Array",
    parameterise=_make_array_parameterise(wtypes.ReferenceArray),
)

GenericImmutableArrayType: typing.Final = _GenericType(
    name="algopy._array.ImmutableArray",
    parameterise=_make_array_parameterise(wtypes.StackArray),
)

GenericARC4DynamicArrayType: typing.Final = _GenericType(
    name="algopy.arc4.DynamicArray",
    parameterise=_make_array_parameterise(wtypes.ARC4DynamicArray),
)
ARC4DynamicBytesType: typing.Final = _register_builtin(
    ArrayType(
        name="algopy.arc4.DynamicBytes",
        wtype=wtypes.ARC4DynamicArray(element_type=ARC4ByteType.wtype, source_location=None),
        size=None,
        items=ARC4ByteType,
        items_wtype=ARC4ByteType.wtype,
        bases=[GenericARC4DynamicArrayType.parameterise([ARC4ByteType], source_location=None)],
        mro=[GenericARC4DynamicArrayType.parameterise([ARC4ByteType], source_location=None)],
        source_location=None,
    )
)


def _parameterise_arc4_static_array(
    self: _GenericType[ArrayType], args: _TypeArgs, source_location: SourceLocation | None
) -> ArrayType:
    try:
        items, size_t = args
    except ValueError:
        raise CodeError(
            f"expected a single type parameter, got {len(args)} parameters", source_location
        ) from None
    size = _require_int_literal(self, size_t, source_location, position_qualifier="second")
    if size < 0:
        raise CodeError("array size should be non-negative", source_location)

    name = f"{self.name}[{items.name}, {size_t.name}]"
    items_wtype = items.checked_wtype(source_location)

    return ArrayType(
        generic=self,
        name=name,
        size=size,
        items=items,
        wtype=wtypes.ARC4StaticArray(
            element_type=items_wtype, array_size=size, source_location=source_location
        ),
        items_wtype=items_wtype,
        source_location=source_location,
    )


GenericARC4StaticArrayType: typing.Final = _GenericType(
    name="algopy.arc4.StaticArray",
    parameterise=_parameterise_arc4_static_array,
)
ARC4AddressType: typing.Final = _register_builtin(
    ArrayType(
        name="algopy.arc4.Address",
        wtype=wtypes.arc4_address_alias,
        size=32,
        generic=None,
        items=ARC4ByteType,
        items_wtype=ARC4ByteType.wtype,
        bases=[
            GenericARC4StaticArrayType.parameterise(
                [ARC4ByteType, TypingLiteralType(value=32, source_location=None)],
                source_location=None,
            )
        ],
        mro=[
            GenericARC4StaticArrayType.parameterise(
                [ARC4ByteType, TypingLiteralType(value=32, source_location=None)],
                source_location=None,
            )
        ],
        source_location=None,
    )
)


def _make_storage_parameterise(wtype: wtypes.WType) -> _Parameterise[StorageProxyType]:
    def parameterise(
        self: _GenericType[StorageProxyType],
        args: _TypeArgs,
        source_location: SourceLocation | None,
    ) -> StorageProxyType:
        try:
            (arg,) = args
        except ValueError:
            raise CodeError(
                f"expected a single type parameter, got {len(args)} parameters", source_location
            ) from None
        name = f"{self.name}[{arg.name}]"
        content_wtype = arg.checked_wtype(source_location)
        return StorageProxyType(
            generic=self,
            name=name,
            content=arg,
            wtype=wtype,
            content_wtype=content_wtype,
        )

    return parameterise


def _parameterise_storage_map(
    self: _GenericType[StorageMapProxyType],
    args: _TypeArgs,
    source_location: SourceLocation | None,
) -> StorageMapProxyType:
    try:
        key, content = args
    except ValueError:
        raise CodeError(
            f"expected two type parameters, got {len(args)} parameters", source_location
        ) from None
    name = f"{self.name}[{key.name}, {content.name}]"
    key_wtype = key.checked_wtype(source_location)
    content_wtype = content.checked_wtype(source_location)
    return StorageMapProxyType(
        generic=self,
        name=name,
        key=key,
        content=content,
        wtype=wtypes.box_key,
        key_wtype=key_wtype,
        content_wtype=content_wtype,
    )


GenericGlobalStateType: typing.Final = _GenericType(
    name="algopy._state.GlobalState",
    parameterise=_make_storage_parameterise(wtypes.state_key),
)
GenericLocalStateType: typing.Final = _GenericType(
    name="algopy._state.LocalState",
    parameterise=_make_storage_parameterise(wtypes.state_key),
)
GenericBoxType: typing.Final = _GenericType(
    name="algopy._box.Box",
    parameterise=_make_storage_parameterise(wtypes.box_key),
)
BoxRefType: typing.Final = _register_builtin(
    StorageProxyType(
        name="algopy._box.BoxRef",
        content=BytesType,
        content_wtype=BytesType.wtype,
        wtype=wtypes.box_key,
        generic=None,
    )
)

GenericBoxMapType: typing.Final = _GenericType(
    name="algopy._box.BoxMap",
    parameterise=_parameterise_storage_map,
)


@attrs.frozen(order=False)
class TransactionRelatedType(PyType, abc.ABC):
    transaction_type: TransactionType | None
    """None implies "any" type, which may be considered as either union or an intersection"""

    def __attrs_post_init__(self) -> None:
        _register_builtin(self)


@typing.final
@attrs.frozen(order=False)
class GroupTransactionType(TransactionRelatedType):
    wtype: wtypes.WGroupTransaction


@typing.final
@attrs.frozen(order=False)
class InnerTransactionFieldsetType(TransactionRelatedType):
    wtype: wtypes.WInnerTransactionFields


@typing.final
@attrs.frozen(order=False)
class InnerTransactionResultType(TransactionRelatedType):
    wtype: wtypes.WInnerTransaction


GroupTransactionBaseType: typing.Final = GroupTransactionType(
    name="algopy.gtxn.TransactionBase",
    wtype=wtypes.WGroupTransaction(name="group_transaction_base", transaction_type=None),
    transaction_type=None,
)


def _make_gtxn_type(kind: TransactionType | None) -> GroupTransactionType:
    if kind is None:
        cls_name = "Transaction"
    else:
        cls_name = f"{_TXN_TYPE_NAMES[kind]}Transaction"
    stub_name = f"algopy.gtxn.{cls_name}"
    return GroupTransactionType(
        name=stub_name,
        transaction_type=kind,
        wtype=wtypes.WGroupTransaction(kind),
        bases=[GroupTransactionBaseType],
        mro=[GroupTransactionBaseType],
    )


def _make_itxn_fieldset_type(kind: TransactionType | None) -> InnerTransactionFieldsetType:
    if kind is None:
        cls_name = "InnerTransaction"
    else:
        cls_name = _TXN_TYPE_NAMES[kind]
    stub_name = f"algopy.itxn.{cls_name}"
    return InnerTransactionFieldsetType(
        name=stub_name,
        transaction_type=kind,
        wtype=wtypes.WInnerTransactionFields(kind),
    )


def _make_itxn_result_type(kind: TransactionType | None) -> InnerTransactionResultType:
    if kind is None:
        cls_name = "InnerTransactionResult"
    else:
        cls_name = f"{_TXN_TYPE_NAMES[kind]}InnerTransaction"
    stub_name = f"algopy.itxn.{cls_name}"
    return InnerTransactionResultType(
        name=stub_name,
        transaction_type=kind,
        wtype=wtypes.WInnerTransaction(kind),
    )


_TXN_TYPE_NAMES: typing.Final[Mapping[TransactionType, str]] = {
    TransactionType.pay: "Payment",
    TransactionType.keyreg: "KeyRegistration",
    TransactionType.acfg: "AssetConfig",
    TransactionType.axfer: "AssetTransfer",
    TransactionType.afrz: "AssetFreeze",
    TransactionType.appl: "ApplicationCall",
}

_all_txn_kinds: typing.Final[Sequence[TransactionType | None]] = [
    None,
    *TransactionType,
]
GroupTransactionTypes: typing.Final[Mapping[TransactionType | None, GroupTransactionType]] = {
    kind: _make_gtxn_type(kind) for kind in _all_txn_kinds
}
InnerTransactionFieldsetTypes: typing.Final[
    Mapping[TransactionType | None, InnerTransactionFieldsetType]
] = {kind: _make_itxn_fieldset_type(kind) for kind in _all_txn_kinds}
InnerTransactionResultTypes: typing.Final[
    Mapping[TransactionType | None, InnerTransactionResultType]
] = {kind: _make_itxn_result_type(kind) for kind in _all_txn_kinds}


@attrs.frozen(kw_only=True, order=False)
class _CompileTimeType(PyType):
    _wtype_error: str

    @typing.override
    @property
    def wtype(self) -> ErrorMessage:
        msg = self._wtype_error.format(self=self)
        return ErrorMessage(msg)

    def __attrs_post_init__(self) -> None:
        _register_builtin(self)


BytesBackedType: typing.Final[PyType] = _CompileTimeType(
    name="algopy._primitives.BytesBacked",
    wtype_error="{self} is not usable as a runtime type",
)


@attrs.frozen(kw_only=True, order=False)
class IntrinsicEnumType(PyType):
    generic: None = attrs.field(default=None, init=False)
    bases: tuple[PyType, ...] = attrs.field(
        default=(StrLiteralType,),  # strictly true, but not sure if we want this?
        init=False,
    )
    mro: tuple[PyType, ...] = attrs.field(default=(StrLiteralType,), init=False)
    members: immutabledict[str, str] = attrs.field(converter=immutabledict)

    @property
    def wtype(self) -> ErrorMessage:
        return ErrorMessage(f"{self} is only valid as a literal argument to an algopy.op function")


def _make_intrinsic_enum_types() -> Sequence[IntrinsicEnumType]:
    from puyapy.awst_build.intrinsic_data import ENUM_CLASSES

    return [
        _register_builtin(
            IntrinsicEnumType(
                name="".join((constants.ALGOPY_OP_PREFIX, cls_name)),
                members=cls_members,
            )
        )
        for cls_name, cls_members in ENUM_CLASSES.items()
    ]


@attrs.frozen(kw_only=True, order=False)
class IntrinsicNamespaceType(PyType):
    generic: None = attrs.field(default=None, init=False)
    bases: tuple[PyType, ...] = attrs.field(default=(), init=False)
    mro: tuple[PyType, ...] = attrs.field(default=(), init=False)
    members: immutabledict[str, PropertyOpMapping | OpMappingWithOverloads] = attrs.field(
        converter=immutabledict
    )

    @property
    def wtype(self) -> ErrorMessage:
        return ErrorMessage(f"{self} is a namespace type only and not usable at runtime")


def _make_intrinsic_namespace_types() -> Sequence[IntrinsicNamespaceType]:
    from puyapy.awst_build.intrinsic_data import NAMESPACE_CLASSES

    return [
        _register_builtin(
            IntrinsicNamespaceType(
                name="".join((constants.ALGOPY_OP_PREFIX, cls_name)),
                members=cls_members,
            )
        )
        for cls_name, cls_members in NAMESPACE_CLASSES.items()
    ]


OpEnumTypes: typing.Final = _make_intrinsic_enum_types()
OpNamespaceTypes: typing.Final = _make_intrinsic_namespace_types()

StateTotalsType: typing.Final[PyType] = _CompileTimeType(
    name="algopy._contract.StateTotals",
    wtype_error="{self} is only usable in a class options context",
)

urangeType: typing.Final[PyType] = _CompileTimeType(  # noqa: N816
    name=constants.URANGE,
    wtype_error="{self} is not usable at runtime",
)


def _parameterise_any_compile_time(
    self: _GenericType,
    args: _TypeArgs,
    source_location: SourceLocation | None,  # noqa: ARG001
) -> PyType:
    arg_names = [arg.name for arg in args]
    name = f"{self.name}[{', '.join(arg_names)}]"
    return _CompileTimeType(name=name, generic=self, wtype_error="{self} is not usable at runtime")


reversedGenericType: typing.Final[PyType] = _GenericType(  # noqa: N816
    name="builtins.reversed",
    parameterise=_parameterise_any_compile_time,
)
uenumerateGenericType: typing.Final[PyType] = _GenericType(  # noqa: N816
    name="algopy._unsigned_builtins.uenumerate",
    parameterise=_parameterise_any_compile_time,
)


LogicSigType: typing.Final[PyType] = _CompileTimeType(
    name="algopy._logic_sig.LogicSig",
    wtype_error="{self} is only usable in a static context",
)


ContractBaseType: typing.Final[PyType] = _BaseType(name=constants.CONTRACT_BASE)
ARC4ContractBaseType: typing.Final[PyType] = _BaseType(
    name=constants.ARC4_CONTRACT_BASE,
    bases=[ContractBaseType],
    mro=[ContractBaseType],
)
ARC4ClientBaseType: typing.Final[PyType] = _BaseType(name="algopy.arc4.ARC4Client")
ARC4StructBaseType: typing.Final[PyType] = _BaseType(name="algopy.arc4.Struct")
StructBaseType: typing.Final[PyType] = _BaseType(name="algopy._struct.Struct")


@typing.final
@attrs.frozen(order=False)
class PseudoGenericFunctionType(PyType):
    return_type: PyType
    generic: _GenericType[PseudoGenericFunctionType]
    bases: tuple[PyType, ...] = attrs.field(default=(), init=False)
    mro: tuple[PyType, ...] = attrs.field(default=(), init=False)

    @property
    def wtype(self) -> ErrorMessage:
        return ErrorMessage(f"{self} is not a value")


def _parameterise_pseudo_generic_function_type(
    self: _GenericType[PseudoGenericFunctionType],
    args: _TypeArgs,
    source_location: SourceLocation | None,
) -> PseudoGenericFunctionType:
    try:
        (arg,) = args
    except ValueError:
        raise CodeError(
            f"expected a single type parameter, got {len(args)} parameters", source_location
        ) from None
    name = f"{self.name}[{arg.name}]"
    return PseudoGenericFunctionType(generic=self, name=name, return_type=arg)


GenericABICallWithReturnType: typing.Final[PyType] = _GenericType(
    name="algopy.arc4._ABICallWithReturnProtocol",
    parameterise=_parameterise_pseudo_generic_function_type,
)
GenericTemplateVarType: typing.Final[PyType] = _GenericType(
    name="algopy._template_variables._TemplateVarMethod",
    parameterise=_parameterise_pseudo_generic_function_type,
)
