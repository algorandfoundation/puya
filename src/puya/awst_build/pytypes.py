from __future__ import annotations

import abc
import typing
from collections.abc import Callable, Iterable, Mapping, Sequence
from functools import cached_property

import attrs
from immutabledict import immutabledict

from puya import log
from puya.awst import wtypes
from puya.awst_build import constants
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation
from puya.utils import lazy_setdefault

logger = log.get_logger(__name__)


@attrs.frozen(kw_only=True, str=False)
class PyType(abc.ABC):
    name: str
    """The canonical fully qualified type name"""
    generic: _GenericType | None = None
    """The generic type that this type was parameterised from, if any."""
    bases: Sequence[PyType] = attrs.field(default=(), converter=tuple["PyType", ...])
    """Direct base classes. probably excluding the implicit builtins.object?"""
    mro: Sequence[PyType] = attrs.field(default=(), converter=tuple["PyType", ...])
    """All base cases, in Method Resolution Order"""

    @bases.validator
    def _bases_validate(self, _attribute: object, bases: Sequence[PyType]) -> None:
        if len(set(bases)) != len(bases):
            raise InternalError(f"Duplicate bases in {self}: [{', '.join(map(str, bases))}]")

    @mro.validator
    def _mro_validate(self, _attribute: object, mro: Sequence[PyType]) -> None:
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
        return result

    def __str__(self) -> str:
        return self._friendly_name

    @property
    @abc.abstractmethod
    def wtype(self) -> wtypes.WType:
        """The WType that this type represents, if any."""

    def parameterise(
        self,
        args: Sequence[PyType | TypingLiteralValue],  # noqa: ARG002
        source_location: SourceLocation | None,
    ) -> PyType:
        """Produce parameterised type.
        Throws if not a generic type of if a parameterised generic type."""
        if self.generic:
            raise CodeError(f"Type already has parameters: {self}", source_location)
        raise CodeError(f"Not a generic type: {self}", source_location)


_builtins_registry: typing.Final = dict[str, PyType]()


_TPyType = typing.TypeVar("_TPyType", bound=PyType)


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
TypeArg: typing.TypeAlias = PyType | TypingLiteralValue
TypeArgs: typing.TypeAlias = tuple[TypeArg, ...]
Parameterise: typing.TypeAlias = Callable[
    ["_GenericType", TypeArgs, SourceLocation | None], PyType
]


@typing.final
@attrs.frozen
class _GenericType(PyType, abc.ABC):
    """Represents a typing.Generic type with unknown parameters"""

    _parameterise: Parameterise
    _instance_cache: dict[TypeArgs, PyType] = attrs.field(factory=dict, eq=False)

    def __attrs_post_init__(self) -> None:
        _register_builtin(self)

    @typing.override
    @property
    def wtype(self) -> typing.Never:
        raise CodeError("Generic type usage requires parameters")

    @typing.override
    def parameterise(
        self, args: Sequence[PyType | TypingLiteralValue], source_location: SourceLocation | None
    ) -> PyType:
        return lazy_setdefault(
            self._instance_cache,
            key=tuple(args),
            default=lambda args_: self._parameterise(self, args_, source_location),
        )


@attrs.frozen
class TypeType(PyType):
    typ: PyType

    @typing.override
    @property
    def wtype(self) -> typing.Never:
        raise CodeError("type objects are not usable as values")


def _parameterise_type_type(
    self: _GenericType, args: TypeArgs, source_location: SourceLocation | None
) -> TypeType:
    try:
        (arg,) = args
    except ValueError:
        raise CodeError(
            f"Expected a single type parameter, got {len(args)} parameters", source_location
        ) from None
    if not isinstance(arg, PyType):
        raise CodeError(f"typing.Literal cannot be used to parameterise {self}", source_location)
    name = f"{self.name}[{arg.name}]"
    return TypeType(name=name, typ=arg, generic=self)


GenericTypeType: typing.Final[PyType] = _GenericType(
    name="builtins.type",
    parameterise=_parameterise_type_type,
)


@attrs.frozen
class TupleType(PyType):
    generic: _GenericType
    items: tuple[PyType, ...] = attrs.field(validator=attrs.validators.min_len(1))
    wtype: wtypes.WType


@attrs.frozen
class ArrayType(PyType):
    generic: _GenericType
    items: PyType
    size: int | None
    wtype: wtypes.WType


@attrs.frozen
class StorageProxyType(PyType):
    content: PyType
    wtype: wtypes.WType


@attrs.frozen
class StorageMapProxyType(PyType):
    generic: _GenericType
    key: PyType
    content: PyType
    wtype: wtypes.WType


@typing.final
@attrs.frozen
class StaticType(PyType):
    @typing.override
    @property
    def wtype(self) -> typing.Never:
        raise CodeError(f"{self} is only usable as a type and cannot be instantiated")


@typing.final
@attrs.frozen(init=False)
class StructType(PyType):
    fields: Mapping[str, PyType] = attrs.field(
        converter=immutabledict, validator=[attrs.validators.min_len(1)]
    )
    frozen: bool
    wtype: wtypes.WType
    source_location: SourceLocation | None
    generic: None = None

    @cached_property
    def names(self) -> Sequence[str]:
        return tuple(self.fields.keys())

    @cached_property
    def types(self) -> Sequence[PyType]:
        return tuple(self.fields.values())

    def __init__(
        self,
        *,
        base: PyType,
        name: str,
        fields: Mapping[str, PyType],
        frozen: bool,
        source_location: SourceLocation | None,
    ):
        field_wtypes = {name: field_typ.wtype for name, field_typ in fields.items()}
        # TODO: this is a bit of a kludge
        wtype_cls: Callable[
            [str, Mapping[str, wtypes.WType], bool, SourceLocation | None], wtypes.WType
        ]
        if base is ARC4StructBaseType:
            wtype_cls = wtypes.ARC4Struct
        elif base is StructBaseType:
            wtype_cls = wtypes.WStructType
        else:
            raise InternalError(f"Unknown struct base type: {base}", source_location)
        wtype = wtype_cls(name, field_wtypes, frozen, source_location)
        self.__attrs_init__(
            bases=[base],
            mro=[base],
            name=name,
            wtype=wtype,
            fields=fields,
            frozen=frozen,
            source_location=source_location,
        )


@typing.final
@attrs.frozen
class _SimpleType(PyType):
    wtype: wtypes.WType

    def __attrs_post_init__(self) -> None:
        _register_builtin(self)


@typing.final
@attrs.frozen
class _LiteralOnlyType(PyType):
    @typing.override
    @property
    def wtype(self) -> typing.Never:
        raise CodeError(f"Python literals of type {self} cannot be used as runtime values")

    def __attrs_post_init__(self) -> None:
        _register_builtin(self)


NoneType: typing.Final[PyType] = _SimpleType(name="builtins.None", wtype=wtypes.void_wtype)
BoolType: typing.Final[PyType] = _SimpleType(name="builtins.bool", wtype=wtypes.bool_wtype)
IntLiteralType: typing.Final[PyType] = _LiteralOnlyType(name="builtins.int")
StrLiteralType: typing.Final[PyType] = _LiteralOnlyType(name="builtins.str")
BytesLiteralType: typing.Final[PyType] = _LiteralOnlyType(name="builtins.bytes")

UInt64Type: typing.Final[PyType] = _SimpleType(
    name=constants.CLS_UINT64,
    wtype=wtypes.uint64_wtype,
)
BigUIntType: typing.Final[PyType] = _SimpleType(
    name=constants.CLS_BIGUINT,
    wtype=wtypes.biguint_wtype,
)
BytesType: typing.Final[PyType] = _SimpleType(
    name=constants.CLS_BYTES,
    wtype=wtypes.bytes_wtype,
)
StringType: typing.Final[PyType] = _SimpleType(
    name=constants.CLS_STRING,
    wtype=wtypes.string_wtype,
)
AccountType: typing.Final[PyType] = _SimpleType(
    name=constants.CLS_ACCOUNT,
    wtype=wtypes.account_wtype,
)
AssetType: typing.Final[PyType] = _SimpleType(
    name=constants.CLS_ASSET,
    wtype=wtypes.asset_wtype,
)
ApplicationType: typing.Final[PyType] = _SimpleType(
    name=constants.CLS_APPLICATION,
    wtype=wtypes.application_wtype,
)
BytesBackedType: typing.Final[PyType] = _SimpleType(
    name=f"{constants.ALGOPY_PREFIX}_primitives.BytesBacked",
    wtype=wtypes.bytes_wtype,
)

OnCompleteActionType: typing.Final[PyType] = _SimpleType(
    name=constants.ENUM_CLS_ON_COMPLETE_ACTION,
    wtype=wtypes.uint64_wtype,
)
TransactionType: typing.Final[PyType] = _SimpleType(
    name=constants.ENUM_CLS_TRANSACTION_TYPE,
    wtype=wtypes.uint64_wtype,
)
OpUpFeeSourceType: typing.Final[PyType] = _SimpleType(
    name=constants.OP_UP_FEE_SOURCE,
    wtype=wtypes.uint64_wtype,
)

ARC4StringType: typing.Final[PyType] = _SimpleType(
    name=constants.CLS_ARC4_STRING,
    wtype=wtypes.arc4_string_wtype,
)
ARC4BoolType: typing.Final[PyType] = _SimpleType(
    name=constants.CLS_ARC4_BOOL,
    wtype=wtypes.arc4_bool_wtype,
)
ARC4DynamicBytesType: typing.Final[PyType] = _SimpleType(
    name=constants.CLS_ARC4_DYNAMIC_BYTES,
    wtype=wtypes.arc4_dynamic_bytes,
)
ARC4AddressType: typing.Final[PyType] = _SimpleType(
    name=constants.CLS_ARC4_ADDRESS,
    wtype=wtypes.arc4_address_type,
)


@attrs.frozen
class ARC4UIntNType(PyType):
    generic: _GenericType
    bits: int
    wtype: wtypes.WType


def _make_arc4_unsigned_int_parameterise(*, max_bits: int | None = None) -> Parameterise:
    def parameterise(
        self: _GenericType, args: TypeArgs, source_location: SourceLocation | None
    ) -> ARC4UIntNType:
        try:
            (bits,) = args
        except ValueError:
            raise CodeError(
                f"Expected a single type parameter, got {len(args)} parameters", source_location
            ) from None
        if not isinstance(bits, int):
            raise CodeError(f"{self} expects a typing.Literal[int] parameter", source_location)
        if (max_bits is not None) and bits > max_bits:
            raise CodeError(f"Max bit size of {self} is {max_bits}, got {bits}", source_location)

        name = f"{self.name}[typing.Literal[{bits}]]"
        return ARC4UIntNType(
            generic=self,
            name=name,
            bits=bits,
            wtype=wtypes.ARC4UIntN(bits, source_location),
        )

    return parameterise


GenericARC4UIntNType: typing.Final = _GenericType(
    name=constants.CLS_ARC4_UINTN,
    parameterise=_make_arc4_unsigned_int_parameterise(max_bits=64),
)
GenericARC4BigUIntNType: typing.Final = _GenericType(
    name=constants.CLS_ARC4_BIG_UINTN,
    parameterise=_make_arc4_unsigned_int_parameterise(),
)


ARC4ByteType: typing.Final[PyType] = _register_builtin(
    ARC4UIntNType(
        generic=GenericARC4UIntNType,
        name=constants.CLS_ARC4_BYTE,
        wtype=wtypes.arc4_byte_type,
        bits=8,
    )
)

ARC4UIntN_Aliases: typing.Final = immutabledict[int, ARC4UIntNType](
    {
        (_bits := 2**_exp): _register_builtin(
            (GenericARC4UIntNType if _bits <= 64 else GenericARC4BigUIntNType).parameterise(
                [_bits], source_location=None
            ),
            alias=f"{constants.ARC4_PREFIX}UInt{_bits}",
        )
        for _exp in range(3, 10)
    }
)


@attrs.frozen
class ARC4UFixedNxMType(PyType):
    generic: _GenericType
    bits: int
    precision: int
    wtype: wtypes.WType


def _make_arc4_unsigned_fixed_parameterise(*, max_bits: int | None = None) -> Parameterise:
    def parameterise(
        self: _GenericType, args: TypeArgs, source_location: SourceLocation | None
    ) -> ARC4UFixedNxMType:
        try:
            bits, precision = args
        except ValueError:
            raise CodeError(
                f"Expected two type parameters, got {len(args)} parameters", source_location
            ) from None
        if not (isinstance(bits, int) and isinstance(precision, int)):
            raise CodeError(f"{self} expects two typing.Literal[int] parameters", source_location)
        if (max_bits is not None) and bits > max_bits:
            raise CodeError(f"Max bit size of {self} is {max_bits}, got {bits}", source_location)

        name = f"{self.name}[typing.Literal[{bits}], typing.Literal[{precision}]]"
        return ARC4UFixedNxMType(
            generic=self,
            name=name,
            bits=bits,
            precision=precision,
            wtype=wtypes.ARC4UFixedNxM(bits, precision, source_location),
        )

    return parameterise


GenericARC4UFixedNxMType: typing.Final = _GenericType(
    name=constants.CLS_ARC4_UFIXEDNXM,
    parameterise=_make_arc4_unsigned_fixed_parameterise(max_bits=64),
)
GenericARC4BigUFixedNxMType: typing.Final = _GenericType(
    name=constants.CLS_ARC4_BIG_UFIXEDNXM,
    parameterise=_make_arc4_unsigned_fixed_parameterise(),
)


def _make_tuple_parameterise(
    typ: Callable[[Iterable[wtypes.WType], SourceLocation | None], wtypes.WType]
) -> Parameterise:
    def parameterise(
        self: _GenericType, args: TypeArgs, source_location: SourceLocation | None
    ) -> TupleType:
        py_types = []
        item_wtypes = []
        for arg in args:
            if not isinstance(arg, PyType):
                raise CodeError(
                    "typing.Literal cannot be used as tuple type parameter", source_location
                )
            item_wtype = arg.wtype
            if item_wtype is None:
                raise CodeError(f"Type {arg} is not allowed in a tuple", source_location)
            py_types.append(arg)
            item_wtypes.append(item_wtype)

        name = f"{self.name}[{', '.join(pyt.name for pyt in py_types)}]"
        return TupleType(
            generic=self,
            name=name,
            items=tuple(py_types),
            wtype=typ(item_wtypes, source_location),
        )

    return parameterise


GenericTupleType: typing.Final = _GenericType(
    name="builtins.tuple",
    parameterise=_make_tuple_parameterise(wtypes.WTuple),
)

GenericARC4TupleType: typing.Final = _GenericType(
    name=constants.CLS_ARC4_TUPLE,
    parameterise=_make_tuple_parameterise(wtypes.ARC4Tuple),
)


def _make_array_parameterise(
    typ: Callable[[wtypes.WType, SourceLocation | None], wtypes.WType]
) -> Parameterise:
    def parameterise(
        self: _GenericType, args: TypeArgs, source_location: SourceLocation | None
    ) -> ArrayType:
        try:
            (arg,) = args
        except ValueError:
            raise CodeError(
                f"Expected a single type parameter, got {len(args)} parameters", source_location
            ) from None
        if not isinstance(arg, PyType):
            raise CodeError(
                f"typing.Literal cannot be used to parameterise {self}", source_location
            )

        name = f"{self.name}[{arg.name}]"
        return ArrayType(
            generic=self,
            name=name,
            size=None,
            items=arg,
            wtype=typ(arg.wtype, source_location),
        )

    return parameterise


GenericArrayType: typing.Final = _GenericType(
    name=constants.CLS_ARRAY,
    parameterise=_make_array_parameterise(wtypes.WArray),
)

GenericARC4DynamicArrayType: typing.Final = _GenericType(
    name=constants.CLS_ARC4_DYNAMIC_ARRAY,
    parameterise=_make_array_parameterise(wtypes.ARC4DynamicArray),
)


def _make_fixed_array_parameterise(
    typ: Callable[[wtypes.WType, int, SourceLocation | None], wtypes.WType]
) -> Parameterise:
    def parameterise(
        self: _GenericType, args: TypeArgs, source_location: SourceLocation | None
    ) -> ArrayType:
        try:
            items, size = args
        except ValueError:
            raise CodeError(
                f"Expected a single type parameter, got {len(args)} parameters", source_location
            ) from None
        if not isinstance(items, PyType):
            raise CodeError(f"{self} expects first parameter to be a type", source_location)
        if not isinstance(size, int):
            raise CodeError(
                f"{self} expects second parameter to be a typing.Literal[int]",
                source_location,
            )
        if size < 0:
            raise CodeError("Array size should be non-negative", source_location)

        name = f"{self.name}[{items.name}, typing.Literal[{size}]]"
        return ArrayType(
            generic=self,
            name=name,
            size=size,
            items=items,
            wtype=typ(items.wtype, size, source_location),
        )

    return parameterise


GenericARC4StaticArrayType: typing.Final = _GenericType(
    name=constants.CLS_ARC4_STATIC_ARRAY,
    parameterise=_make_fixed_array_parameterise(wtypes.ARC4StaticArray),
)


def _make_storage_parameterise(key_type: wtypes.WType) -> Parameterise:
    def parameterise(
        self: _GenericType, args: TypeArgs, source_location: SourceLocation | None
    ) -> StorageProxyType:
        try:
            (arg,) = args
        except ValueError:
            raise CodeError(
                f"Expected a single type parameter, got {len(args)} parameters", source_location
            ) from None
        if not isinstance(arg, PyType):
            raise CodeError(
                f"typing.Literal cannot be used to parameterise {self}", source_location
            )

        name = f"{self.name}[{arg.name}]"
        return StorageProxyType(
            generic=self,
            name=name,
            content=arg,
            wtype=key_type,
        )

    return parameterise


def _make_storage_parameterise_todo_remove_me(
    key_type: Callable[[wtypes.WType], wtypes.WType]
) -> Parameterise:
    def parameterise(
        self: _GenericType, args: TypeArgs, source_location: SourceLocation | None
    ) -> StorageProxyType:
        try:
            (arg,) = args
        except ValueError:
            raise CodeError(
                f"Expected a single type parameter, got {len(args)} parameters", source_location
            ) from None
        if not isinstance(arg, PyType):
            raise CodeError(
                f"typing.Literal cannot be used to parameterise {self}", source_location
            )

        name = f"{self.name}[{arg.name}]"
        return StorageProxyType(
            generic=self,
            name=name,
            content=arg,
            wtype=key_type(arg.wtype),
        )

    return parameterise


def _parameterise_storage_map(
    self: _GenericType, args: TypeArgs, source_location: SourceLocation | None
) -> StorageMapProxyType:
    try:
        key, content = args
    except ValueError:
        raise CodeError(
            f"Expected two type parameters, got {len(args)} parameters", source_location
        ) from None
    if not isinstance(key, PyType):
        raise CodeError(f"typing.Literal cannot be used to parameterise {self}", source_location)
    if not isinstance(content, PyType):
        raise CodeError(f"typing.Literal cannot be used to parameterise {self}", source_location)

    name = f"{self.name}[{key.name}, {content.name}]"
    return StorageMapProxyType(
        generic=self,
        name=name,
        key=key,
        content=content,
        # TODO: maybe bytes since it will just be the prefix?
        #       would have to change strategy in _gather_global_direct_storages if so
        # wtype=wtypes.box_key,
        # TODO: FIXME
        wtype=wtypes.WBoxMapProxy.from_key_and_content_type(key.wtype, content.wtype),
    )


GenericGlobalStateType: typing.Final = _GenericType(
    name=constants.CLS_GLOBAL_STATE,
    parameterise=_make_storage_parameterise(wtypes.state_key),
)
GenericLocalStateType: typing.Final = _GenericType(
    name=constants.CLS_LOCAL_STATE,
    parameterise=_make_storage_parameterise(wtypes.state_key),
)
GenericBoxType: typing.Final = _GenericType(
    name=constants.CLS_BOX_PROXY,
    # TODO: FIXME
    # parameterise=_make_storage_parameterise(wtypes.box_key),
    parameterise=_make_storage_parameterise_todo_remove_me(wtypes.WBoxProxy.from_content_type),
)
BoxRefType: typing.Final = _register_builtin(
    StorageProxyType(
        name=constants.CLS_BOX_REF_PROXY,
        content=BytesType,
        # wtype=wtypes.box_key,
        wtype=wtypes.box_ref_proxy_type,  # TODO: fixme
        generic=None,
    )
)

GenericBoxMapType: typing.Final = _GenericType(
    name=constants.CLS_BOX_MAP_PROXY,
    parameterise=_parameterise_storage_map,
)


GroupTransactionBaseType: typing.Final[PyType] = _SimpleType(
    name=constants.CLS_TRANSACTION_BASE,
    wtype=wtypes.WGroupTransaction(
        transaction_type=None,
        stub_name=constants.CLS_TRANSACTION_BASE,
        name="group_transaction_base",
    ),
)


def _make_txn_types(kind: constants.TransactionType | None) -> tuple[PyType, PyType, PyType]:
    gtxn_type = _make_gtxn_type(kind)
    itxn_fieldset_type = _make_itxn_fieldset_type(kind)
    itxn_result_type = _make_itxn_result_type(kind)
    return gtxn_type, itxn_fieldset_type, itxn_result_type


def _make_gtxn_type(kind: constants.TransactionType | None) -> PyType:
    if kind is None:
        wtype_name = "group_transaction"
        cls_name = "Transaction"
    else:
        wtype_name = f"group_transaction_{kind.name}"
        cls_name = f"{_TXN_TYPE_NAMES[kind]}Transaction"
    stub_name = f"{constants.ALGOPY_PREFIX}gtxn.{cls_name}"
    return _SimpleType(
        name=stub_name,
        wtype=wtypes.WGroupTransaction(
            name=wtype_name,
            transaction_type=kind,
            stub_name=stub_name,
        ),
    )


def _make_itxn_fieldset_type(kind: constants.TransactionType | None) -> PyType:
    if kind is None:
        wtype_name = "inner_transaction_fields"
        cls_name = "InnerTransaction"
    else:
        wtype_name = f"inner_transaction_fields_{kind.name}"
        cls_name = _TXN_TYPE_NAMES[kind]
    stub_name = f"{constants.ALGOPY_PREFIX}itxn.{cls_name}"
    return _SimpleType(
        name=stub_name,
        wtype=wtypes.WInnerTransactionFields(
            name=wtype_name, transaction_type=kind, stub_name=stub_name
        ),
    )


def _make_itxn_result_type(kind: constants.TransactionType | None) -> PyType:
    if kind is None:
        wtype_name = "inner_transaction"
        cls_name = "InnerTransactionResult"
    else:
        wtype_name = f"inner_transaction_{kind.name}"
        cls_name = f"{_TXN_TYPE_NAMES[kind]}InnerTransaction"
    stub_name = f"{constants.ALGOPY_PREFIX}itxn.{cls_name}"
    return _SimpleType(
        name=stub_name,
        wtype=wtypes.WInnerTransaction(
            name=wtype_name, transaction_type=kind, stub_name=stub_name
        ),
    )


_TXN_TYPE_NAMES: typing.Final[Mapping[constants.TransactionType, str]] = {
    constants.TransactionType.pay: "Payment",
    constants.TransactionType.keyreg: "KeyRegistration",
    constants.TransactionType.acfg: "AssetConfig",
    constants.TransactionType.axfer: "AssetTransfer",
    constants.TransactionType.afrz: "AssetFreeze",
    constants.TransactionType.appl: "ApplicationCall",
}

_all_txn_kinds: typing.Final[Sequence[constants.TransactionType | None]] = [
    None,
    *constants.TransactionType,
]
GroupTransactionTypes: typing.Final[Mapping[constants.TransactionType | None, PyType]] = {
    kind: _make_gtxn_type(kind) for kind in _all_txn_kinds
}
InnerTransactionFieldsetTypes: typing.Final[Mapping[constants.TransactionType | None, PyType]] = {
    kind: _make_itxn_fieldset_type(kind) for kind in _all_txn_kinds
}
InnerTransactionResultTypes: typing.Final[Mapping[constants.TransactionType | None, PyType]] = {
    kind: _make_itxn_result_type(kind) for kind in _all_txn_kinds
}


@attrs.frozen(kw_only=True)
class _CompileTimeType(PyType):
    _wtype_error: str

    @typing.override
    @property
    def wtype(self) -> typing.Never:
        msg = self._wtype_error.format(self=self)
        raise CodeError(msg)

    def __attrs_post_init__(self) -> None:
        _register_builtin(self)


def _make_op_namespace_types() -> Sequence[PyType]:
    from itertools import chain

    from puya.awst_build.intrinsic_data import ENUM_CLASSES, NAMESPACE_CLASSES

    return [
        _CompileTimeType(
            name="".join((constants.ALGOPY_OP_PREFIX, cls_name)),
            wtype_error="{self} is a namespace type only and not usable at runtime",
        )
        for cls_name in chain(ENUM_CLASSES, NAMESPACE_CLASSES)
    ]


OpNamespaceTypes: typing.Final = _make_op_namespace_types()

StateTotalsType: typing.Final[PyType] = _CompileTimeType(
    name=f"{constants.ALGOPY_PREFIX}_contract.StateTotals",
    wtype_error="{self} is only usable in a class options context",
)

urangeType: typing.Final[PyType] = _CompileTimeType(  # noqa: N816
    name=constants.URANGE,
    wtype_error="{self} is not usable at runtime",
)


def _parameterise_any_compile_time(
    self: _GenericType, args: TypeArgs, source_location: SourceLocation | None  # noqa: ARG001
) -> PyType:
    arg_names = []
    for arg in args:
        if isinstance(arg, PyType):
            arg_names.append(arg.name)
        else:
            arg_names.append(f"typing.Literal[{arg}]")
    name = f"{self.name}[{', '.join(arg_names)}]"
    return _CompileTimeType(name=name, generic=self, wtype_error="{self} is not usable at runtime")


reversedGenericType: typing.Final[PyType] = _GenericType(  # noqa: N816
    name="builtins.reversed",
    parameterise=_parameterise_any_compile_time,
)
uenumerateGenericType: typing.Final[PyType] = _GenericType(  # noqa: N816
    name=constants.UENUMERATE,
    parameterise=_parameterise_any_compile_time,
)


LogicSigType: typing.Final[PyType] = _CompileTimeType(
    name=f"{constants.ALGOPY_PREFIX}_logic_sig.LogicSig",
    wtype_error="{self} is only usable in a static context",
)


@attrs.frozen
class _BaseType(PyType):
    """Type that is only usable as a base type"""

    @typing.override
    @property
    def wtype(self) -> typing.Never:
        raise CodeError(f"{self} is only usable as a base type")

    def __attrs_post_init__(self) -> None:
        _register_builtin(self)


ContractBaseType: typing.Final[PyType] = _BaseType(name=constants.CONTRACT_BASE)
ARC4ContractBaseType: typing.Final[PyType] = _BaseType(
    name=constants.ARC4_CONTRACT_BASE,
    bases=[ContractBaseType],
    mro=[ContractBaseType],
)
ARC4ClientBaseType: typing.Final[PyType] = _BaseType(name=constants.CLS_ARC4_CLIENT)
ARC4StructBaseType: typing.Final[PyType] = _BaseType(name=constants.CLS_ARC4_STRUCT)
StructBaseType: typing.Final[PyType] = _BaseType(name=constants.STRUCT_BASE)
