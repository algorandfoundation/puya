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
from puya.utils import coalesce, lazy_setdefault

logger = log.get_logger(__name__)


@attrs.frozen(kw_only=True)
class PyType(abc.ABC):
    name: str
    """The canonical fully qualified type name"""
    _alias: str | None = None
    """The public fully qualified type name. If not specified, defaults to name."""
    generic: GenericType | None = None
    """The generic type that this type was parameterised from, if any."""

    @property
    def alias(self) -> str:
        return coalesce(self._alias, self.name)

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
            raise CodeError(f"Type already has parameters: {self.alias}", source_location)
        raise CodeError(f"Not a generic type: {self.alias}", source_location)


# Registry used for lookups from mypy types.
_type_registry: typing.Final = dict[str, PyType]()


def _register(typ: PyType) -> None:
    existing_entry = _type_registry.get(typ.name)
    if existing_entry is None:
        _type_registry[typ.name] = typ
    elif existing_entry is typ:
        logger.debug(f"Duplicate registration of {typ}")
    else:
        raise InternalError(f"Duplicate mapping of {typ.name}")


def lookup(name: str) -> PyType | None:
    """Lookup type by the canonical fully qualified name"""
    return _type_registry.get(name)


# https://typing.readthedocs.io/en/latest/spec/literal.html#legal-and-illegal-parameterizations
# We don't support enums as typing.Literal parameters. MyPy encodes these as str values with
# an additional "fallback" data member, but we don't need that complication.
# mypy.types.LiteralValue also includes float, noting its invalid as a parameterization, but
# we exclude this here.
# None types are also encoded as their own type, but we have them as values here.
TypingLiteralValue: typing.TypeAlias = int | bytes | str | bool | None
TypeArg: typing.TypeAlias = PyType | TypingLiteralValue
TypeArgs: typing.TypeAlias = tuple[TypeArg, ...]
Parameterise: typing.TypeAlias = Callable[["GenericType", TypeArgs, SourceLocation | None], PyType]

# Just a cache. Would be better as a class-var on GenericType, but see note on _type_registry
_generic_instances: typing.Final = dict[TypeArgs, PyType]()


@typing.final
@attrs.frozen
class GenericType(PyType, abc.ABC):
    """Represents a typing.Generic type with unknown parameters"""

    _parameterise: Parameterise

    def __attrs_post_init__(self) -> None:
        _register(self)

    @typing.override
    @property
    def wtype(self) -> typing.Never:
        raise CodeError("Generic type usage requires parameters")

    @typing.override
    def parameterise(
        self, args: Sequence[PyType | TypingLiteralValue], source_location: SourceLocation | None
    ) -> PyType:
        return lazy_setdefault(
            _generic_instances,
            key=tuple(args),
            default=lambda args_: self._parameterise(self, args_, source_location),
        )


@attrs.frozen
class TupleType(PyType):
    generic: GenericType
    items: tuple[PyType, ...] = attrs.field(validator=attrs.validators.min_len(1))
    wtype: wtypes.WType


@attrs.frozen
class ArrayType(PyType):
    generic: GenericType
    items: PyType
    size: int | None
    wtype: wtypes.WType


@attrs.frozen
class StorageProxyType(PyType):
    content: PyType
    wtype: wtypes.WType


@attrs.frozen
class StorageMapProxyType(PyType):
    generic: GenericType
    key: PyType
    content: PyType
    wtype: wtypes.WType


@typing.final
@attrs.frozen(init=False)
class StructType(PyType):
    metaclass: str
    fields: Mapping[str, PyType] = attrs.field(
        converter=immutabledict, validator=[attrs.validators.min_len(1)]
    )
    frozen: bool
    wtype: wtypes.WType
    source_location: SourceLocation | None

    @cached_property
    def names(self) -> Sequence[str]:
        return tuple(self.fields.keys())

    @cached_property
    def types(self) -> Sequence[PyType]:
        return tuple(self.fields.values())

    def __init__(
        self,
        metaclass: str,
        typ: Callable[
            [str, Mapping[str, wtypes.WType], bool, SourceLocation | None], wtypes.WType
        ],
        *,
        name: str,
        fields: Mapping[str, PyType],
        frozen: bool,
        source_location: SourceLocation | None,
    ):
        field_wtypes = {}
        for field_name, field_pytype in fields.items():
            field_wtype = field_pytype.wtype
            if field_wtype is None:
                raise CodeError(
                    f"Type {field_pytype.alias} is not allowed in a struct", source_location
                )
            field_wtypes[field_name] = field_wtype
        wtype = typ(name, field_wtypes, frozen, source_location)
        self.__attrs_init__(
            metaclass=metaclass,
            name=name,
            wtype=wtype,
            fields=fields,
            frozen=frozen,
            source_location=source_location,
        )
        _register(self)

    @classmethod
    def native(
        cls,
        *,
        name: str,
        fields: Mapping[str, PyType],
        frozen: bool,
        source_location: SourceLocation | None,
    ) -> typing.Self:
        return cls(
            metaclass=constants.STRUCT_BASE,
            typ=wtypes.WStructType,
            name=name,
            fields=fields,
            frozen=frozen,
            source_location=source_location,
        )

    @classmethod
    def arc4(
        cls,
        *,
        name: str,
        fields: Mapping[str, PyType],
        frozen: bool,
        source_location: SourceLocation | None,
    ) -> typing.Self:
        return cls(
            metaclass=constants.CLS_ARC4_STRUCT_META,
            typ=wtypes.ARC4Struct,
            name=name,
            fields=fields,
            frozen=frozen,
            source_location=source_location,
        )


@typing.final
@attrs.frozen
class _SimpleType(PyType):
    wtype: wtypes.WType

    def __attrs_post_init__(self) -> None:
        _register(self)


NoneType: typing.Final[PyType] = _SimpleType(
    name="builtins.None",
    alias="None",
    wtype=wtypes.void_wtype,
)
BoolType: typing.Final[PyType] = _SimpleType(
    name="builtins.bool",
    alias="bool",
    wtype=wtypes.bool_wtype,
)
UInt64Type: typing.Final[PyType] = _SimpleType(
    name=constants.CLS_UINT64,
    alias=constants.CLS_UINT64_ALIAS,
    wtype=wtypes.uint64_wtype,
)
BigUIntType: typing.Final[PyType] = _SimpleType(
    name=constants.CLS_BIGUINT,
    alias=constants.CLS_BIGUINT_ALIAS,
    wtype=wtypes.biguint_wtype,
)
BytesType: typing.Final[PyType] = _SimpleType(
    name=constants.CLS_BYTES,
    alias=constants.CLS_BYTES_ALIAS,
    wtype=wtypes.bytes_wtype,
)
StringType: typing.Final[PyType] = _SimpleType(
    name=constants.CLS_STRING,
    alias=constants.CLS_STRING_ALIAS,
    wtype=wtypes.string_wtype,
)
AccountType: typing.Final[PyType] = _SimpleType(
    name=constants.CLS_ACCOUNT,
    alias=constants.CLS_ACCOUNT_ALIAS,
    wtype=wtypes.account_wtype,
)
AssetType: typing.Final[PyType] = _SimpleType(
    name=constants.CLS_ASSET,
    alias=constants.CLS_ASSET_ALIAS,
    wtype=wtypes.asset_wtype,
)
ApplicationType: typing.Final[PyType] = _SimpleType(
    name=constants.CLS_APPLICATION,
    alias=constants.CLS_APPLICATION_ALIAS,
    wtype=wtypes.application_wtype,
)
ARC4StringType: typing.Final[PyType] = _SimpleType(
    name=constants.CLS_ARC4_STRING,
    wtype=wtypes.arc4_string_wtype,
)
ARC4BoolType: typing.Final[PyType] = _SimpleType(
    name=constants.CLS_ARC4_BOOL,
    wtype=wtypes.arc4_bool_wtype,
)
ARC4ByteType: typing.Final[PyType] = _SimpleType(
    name=constants.CLS_ARC4_BYTE,
    wtype=wtypes.arc4_byte_type,
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
    generic: GenericType
    bits: int
    wtype: wtypes.WType


def _make_arc4_unsigned_int_parameterise(*, max_bits: int | None = None) -> Parameterise:
    def parameterise(
        self: GenericType, args: TypeArgs, source_location: SourceLocation | None
    ) -> ARC4UIntNType:
        try:
            (bits,) = args
        except ValueError:
            raise CodeError(
                f"Expected a single type parameter, got {len(args)} parameters", source_location
            ) from None
        if not isinstance(bits, int):
            raise CodeError(
                f"{self.alias} expects a typing.Literal[int] parameter", source_location
            )
        if (max_bits is not None) and bits > max_bits:
            raise CodeError(
                f"Max bit size of {self.alias} is {max_bits}, got {bits}", source_location
            )

        name = f"{self.name}[typing.Literal[{bits}]]"
        alias = None
        if bits.bit_count() == 1:  # quick way to check for power of 2
            alias = f"{constants.ARC4_PREFIX}UInt{bits}"
        return ARC4UIntNType(
            generic=self,
            name=name,
            alias=alias,
            bits=bits,
            wtype=wtypes.ARC4UIntN(bits, source_location),
        )

    return parameterise


GenericARC4UIntNType: typing.Final = GenericType(
    name=constants.CLS_ARC4_UINTN,
    parameterise=_make_arc4_unsigned_int_parameterise(max_bits=64),
)
GenericARC4BigUIntNType: typing.Final = GenericType(
    name=constants.CLS_ARC4_BIG_UINTN,
    parameterise=_make_arc4_unsigned_int_parameterise(max_bits=512),
)


@attrs.frozen
class ARC4UFixedNxMType(PyType):
    generic: GenericType
    bits: int
    precision: int
    wtype: wtypes.WType


def _make_arc4_unsigned_fixed_parameterise(*, max_bits: int | None = None) -> Parameterise:
    def parameterise(
        self: GenericType, args: TypeArgs, source_location: SourceLocation | None
    ) -> ARC4UFixedNxMType:
        try:
            bits, precision = args
        except ValueError:
            raise CodeError(
                f"Expected two type parameters, got {len(args)} parameters", source_location
            ) from None
        if not (isinstance(bits, int) and isinstance(precision, int)):
            raise CodeError(
                f"{self.alias} expects two typing.Literal[int] parameters", source_location
            )
        if (max_bits is not None) and bits > max_bits:
            raise CodeError(
                f"Max bit size of {self.alias} is {max_bits}, got {bits}", source_location
            )

        name = f"{self.name}[typing.Literal[{bits}], typing.Literal[{precision}]]"
        return ARC4UFixedNxMType(
            generic=self,
            name=name,
            bits=bits,
            precision=precision,
            wtype=wtypes.ARC4UFixedNxM(bits, precision, source_location),
        )

    return parameterise


GenericARC4UFixedNxMType: typing.Final = GenericType(
    name=constants.CLS_ARC4_UFIXEDNXM,
    parameterise=_make_arc4_unsigned_fixed_parameterise(max_bits=64),
)
GenericARC4BigUFixedNxMType: typing.Final = GenericType(
    name=constants.CLS_ARC4_BIG_UFIXEDNXM,
    parameterise=_make_arc4_unsigned_fixed_parameterise(),
)


def _make_tuple_parameterise(
    typ: Callable[[Iterable[wtypes.WType], SourceLocation | None], wtypes.WType]
) -> Parameterise:
    def parameterise(
        self: GenericType, args: TypeArgs, source_location: SourceLocation | None
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
                raise CodeError(f"Type {arg.alias} is not allowed in a tuple", source_location)
            py_types.append(arg)
            item_wtypes.append(item_wtype)

        name = f"{self.name}[{', '.join(pyt.name for pyt in py_types)}]"
        alias = f"{self.alias}[{', '.join(pyt.alias for pyt in py_types)}]"
        return TupleType(
            generic=self,
            name=name,
            alias=alias,
            items=tuple(py_types),
            wtype=typ(item_wtypes, source_location),
        )

    return parameterise


GenericTupleType: typing.Final = GenericType(
    name="builtins.tuple",
    alias="tuple",
    parameterise=_make_tuple_parameterise(wtypes.WTuple),
)

GenericARC4TupleType: typing.Final = GenericType(
    name=constants.CLS_ARC4_TUPLE,
    parameterise=_make_tuple_parameterise(wtypes.ARC4Tuple),
)


def _make_array_parameterise(
    typ: Callable[[wtypes.WType, SourceLocation | None], wtypes.WType]
) -> Parameterise:
    def parameterise(
        self: GenericType, args: TypeArgs, source_location: SourceLocation | None
    ) -> ArrayType:
        try:
            (arg,) = args
        except ValueError:
            raise CodeError(
                f"Expected a single type parameter, got {len(args)} parameters", source_location
            ) from None
        if not isinstance(arg, PyType):
            raise CodeError(
                f"typing.Literal cannot be used to parameterise {self.alias}", source_location
            )

        name = f"{self.name}[{arg.name}]"
        alias = f"{self.alias}[{arg.alias}]"
        return ArrayType(
            generic=self,
            name=name,
            alias=alias,
            size=None,
            items=arg,
            wtype=typ(arg.wtype, source_location),
        )

    return parameterise


GenericArrayType: typing.Final = GenericType(
    name=constants.CLS_ARRAY,
    alias=constants.CLS_ARRAY_ALIAS,
    parameterise=_make_array_parameterise(wtypes.WArray),
)

GenericARC4DynamicArrayType: typing.Final = GenericType(
    name=constants.CLS_ARC4_DYNAMIC_ARRAY,
    parameterise=_make_array_parameterise(wtypes.ARC4DynamicArray),
)


def _make_fixed_array_parameterise(
    typ: Callable[[wtypes.WType, int, SourceLocation | None], wtypes.WType]
) -> Parameterise:
    def parameterise(
        self: GenericType, args: TypeArgs, source_location: SourceLocation | None
    ) -> ArrayType:
        try:
            items, size = args
        except ValueError:
            raise CodeError(
                f"Expected a single type parameter, got {len(args)} parameters", source_location
            ) from None
        if not isinstance(items, PyType):
            raise CodeError(f"{self.alias} expects first parameter to be a type", source_location)
        if not isinstance(size, int):
            raise CodeError(
                f"{self.alias} expects second parameter to be a typing.Literal[int]",
                source_location,
            )
        if size < 0:
            raise CodeError("Array size should be non-negative", source_location)

        name = f"{self.name}[{items.name}, typing.Literal[{size}]]"
        alias = f"{self.alias}[{items.alias}, typing.Literal[{size}]]"
        return ArrayType(
            generic=self,
            name=name,
            alias=alias,
            size=size,
            items=items,
            wtype=typ(items.wtype, size, source_location),
        )

    return parameterise


GenericARC4StaticArrayType: typing.Final = GenericType(
    name=constants.CLS_ARC4_STATIC_ARRAY,
    parameterise=_make_fixed_array_parameterise(wtypes.ARC4StaticArray),
)


def _make_storage_parameterise(key_type: wtypes.WType) -> Parameterise:
    def parameterise(
        self: GenericType, args: TypeArgs, source_location: SourceLocation | None
    ) -> StorageProxyType:
        try:
            (arg,) = args
        except ValueError:
            raise CodeError(
                f"Expected a single type parameter, got {len(args)} parameters", source_location
            ) from None
        if not isinstance(arg, PyType):
            raise CodeError(
                f"typing.Literal cannot be used to parameterise {self.alias}", source_location
            )

        name = f"{self.name}[{arg.name}]"
        alias = f"{self.alias}[{arg.alias}]"
        return StorageProxyType(
            generic=self,
            name=name,
            alias=alias,
            content=arg,
            wtype=key_type,
        )

    return parameterise


def _parameterise_storage_map(
    self: GenericType, args: TypeArgs, source_location: SourceLocation | None
) -> StorageMapProxyType:
    try:
        key, content = args
    except ValueError:
        raise CodeError(
            f"Expected two type parameters, got {len(args)} parameters", source_location
        ) from None
    if not isinstance(key, PyType):
        raise CodeError(
            f"typing.Literal cannot be used to parameterise {self.alias}", source_location
        )
    if not isinstance(content, PyType):
        raise CodeError(
            f"typing.Literal cannot be used to parameterise {self.alias}", source_location
        )

    name = f"{self.name}[{key.name}, {content.name}]"
    alias = f"{self.alias}[{key.alias}, {content.alias}]"
    return StorageMapProxyType(
        generic=self,
        name=name,
        alias=alias,
        key=key,
        content=content,
        # TODO: maybe bytes since it will just be the prefix?
        #       would have to change strategy in _gather_global_direct_storages if so
        wtype=wtypes.box_key,
    )


GenericGlobalStateType: typing.Final = GenericType(
    name=constants.CLS_GLOBAL_STATE,
    alias=constants.CLS_GLOBAL_STATE_ALIAS,
    parameterise=_make_storage_parameterise(wtypes.state_key),
)
GenericLocalStateType: typing.Final = GenericType(
    name=constants.CLS_LOCAL_STATE,
    alias=constants.CLS_LOCAL_STATE_ALIAS,
    parameterise=_make_storage_parameterise(wtypes.state_key),
)
GenericBoxType: typing.Final = GenericType(
    name=constants.CLS_BOX_PROXY,
    alias=constants.CLS_BOX_PROXY_ALIAS,
    parameterise=_make_storage_parameterise(wtypes.box_key),
)
BoxRefType: typing.Final = StorageProxyType(
    name=constants.CLS_BOX_REF_PROXY,
    alias=constants.CLS_BOX_REF_PROXY_ALIAS,
    content=BytesType,
    wtype=wtypes.box_key,
    generic=None,
)
_register(BoxRefType)

GenericBoxMapType: typing.Final = GenericType(
    name=constants.CLS_BOX_MAP_PROXY,
    alias=constants.CLS_BOX_MAP_PROXY_ALIAS,
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


def _make_txn_types(
    kind: constants.TransactionType | None,
    name: str,
    itxn_fields: str | None = None,
    itxn_result: str | None = None,
) -> tuple[PyType, PyType, PyType]:
    gtxn_name = f"{constants.ALGOPY_PREFIX}gtxn.{name}Transaction"
    itxn_fieldset_name = itxn_fields or f"{constants.ALGOPY_PREFIX}itxn.{name}"
    itxn_result_name = itxn_result or f"{constants.ALGOPY_PREFIX}itxn.{name}InnerTransaction"

    gtxn_type = _SimpleType(
        name=gtxn_name,
        wtype=wtypes.WGroupTransaction(
            stub_name=gtxn_name,
            name="group_transaction" if not kind else f"group_transaction_{kind.name}",
            transaction_type=kind,
        ),
    )

    itxn_fieldset_type = _SimpleType(
        name=itxn_fieldset_name,
        wtype=wtypes.WInnerTransactionFields(
            stub_name=itxn_fieldset_name,
            name=(
                "inner_transaction_fields" if not kind else f"inner_transaction_fields_{kind.name}"
            ),
            transaction_type=kind,
        ),
    )

    itxn_result_type = _SimpleType(
        name=itxn_result_name,
        wtype=wtypes.WInnerTransaction(
            stub_name=itxn_result_name,
            name="inner_transaction" if not kind else f"inner_transaction_{kind.name}",
            transaction_type=kind,
        ),
    )

    return gtxn_type, itxn_fieldset_type, itxn_result_type


# TODO: assign these
_make_txn_types(constants.TransactionType.pay, "Payment")
_make_txn_types(constants.TransactionType.keyreg, "KeyRegistration")
_make_txn_types(constants.TransactionType.acfg, "AssetConfig")
_make_txn_types(constants.TransactionType.axfer, "AssetTransfer")
_make_txn_types(constants.TransactionType.afrz, "AssetFreeze")
_make_txn_types(constants.TransactionType.appl, "ApplicationCall")
_make_txn_types(
    None,
    "",
    f"{constants.ALGOPY_PREFIX}itxn.InnerTransaction",
    f"{constants.ALGOPY_PREFIX}itxn.InnerTransactionResult",
)
