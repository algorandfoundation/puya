from __future__ import annotations

import abc
import typing
from collections.abc import Callable, Iterable, Mapping, Sequence, Iterator
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
    generic: GenericType | None = None
    """The generic type that this type was parameterised from, if any."""
    metaclass: MetaclassType | None = None
    """The metaclass for this type, if different from builtins.type"""

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

    def register(self) -> typing.Self:
        _register(self)
        return self

    def register_alias(self, name: str) -> typing.Self:
        _register(self, alias=name)
        return self


# Registry used for lookups from mypy types.
_type_registry: typing.Final = dict[str, PyType]()


def _register(typ: PyType, *, alias: str | None = None) -> None:
    name = alias or typ.name
    existing_entry = _type_registry.get(name)
    if existing_entry is None:
        _type_registry[name] = typ
    elif existing_entry is typ:
        logger.debug(f"Duplicate registration of {typ}")
    else:
        raise InternalError(f"Duplicate mapping of {name}")


def lookup(name: str) -> PyType | None:
    """Lookup type by the canonical fully qualified name"""
    return _type_registry.get(name)


# https://typing.readthedocs.io/en/latest/spec/literal.html#legal-and-illegal-parameterizations
# We don't support enums as typing.Literal parameters. mypy encodes these as str values with
# an additional "fallback" data member, but we don't need that complication.
# mypy.types.LiteralValue also includes float, noting its invalid as a parameterization, but
# we exclude this here.
# None types are also encoded as their own type, but we have them as values here.
TypingLiteralValue: typing.TypeAlias = int | bytes | str | bool | None
TypeArg: typing.TypeAlias = PyType | TypingLiteralValue
TypeArgs: typing.TypeAlias = tuple[TypeArg, ...]
Parameterise: typing.TypeAlias = Callable[["GenericType", TypeArgs, SourceLocation | None], PyType]


@typing.final
@attrs.frozen
class GenericType(PyType, abc.ABC):
    """Represents a typing.Generic type with unknown parameters"""

    _parameterise: Parameterise
    _instance_cache: dict[TypeArgs, PyType] = attrs.field(factory=dict, eq=False)

    def __attrs_post_init__(self) -> None:
        self.register()

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


@typing.final
@attrs.frozen
class MetaclassType(PyType):
    generic: None = None

    @typing.override
    @property
    def wtype(self) -> typing.Never:
        raise CodeError("Metaclass types are not valid as values")

    def __attrs_post_init__(self) -> None:
        self.register()

    @typing.override
    def parameterise(
        self, args: Sequence[PyType | TypingLiteralValue], source_location: SourceLocation | None
    ) -> typing.Never:
        raise CodeError("Generic metaclass types are not supported", source_location)


ABCMeta: typing.Final = MetaclassType(name="abc.ABCMeta")
StructMeta: typing.Final = MetaclassType(name=constants.STRUCT_META)
ARC4StructMeta: typing.Final = MetaclassType(name=constants.CLS_ARC4_STRUCT_META)


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
        metaclass: MetaclassType,
        typ: Callable[
            [str, Mapping[str, wtypes.WType], bool, SourceLocation | None], wtypes.WType
        ],
        *,
        name: str,
        fields: Mapping[str, PyType],
        frozen: bool,
        source_location: SourceLocation | None,
    ):
        field_wtypes = {name: field_typ.wtype for name, field_typ in fields.items()}
        wtype = typ(name, field_wtypes, frozen, source_location)
        self.__attrs_init__(
            metaclass=metaclass,
            name=name,
            wtype=wtype,
            fields=fields,
            frozen=frozen,
            source_location=source_location,
        )
        self.register()

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
            metaclass=StructMeta,
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
            metaclass=ARC4StructMeta,
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
        self.register()


NoneType: typing.Final[PyType] = _SimpleType(
    name="builtins.None",
    wtype=wtypes.void_wtype,
)
BoolType: typing.Final[PyType] = _SimpleType(
    name="builtins.bool",
    wtype=wtypes.bool_wtype,
)
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

OnCompleteActionType: typing.Final[PyType] = _SimpleType(
    name=constants.ENUM_CLS_ON_COMPLETE_ACTION,
    wtype=wtypes.uint64_wtype,
)
TransactionType: typing.Final[PyType] = _SimpleType(
    name=constants.ENUM_CLS_TRANSACTION_TYPE,
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


GenericARC4UIntNType: typing.Final = GenericType(
    name=constants.CLS_ARC4_UINTN,
    parameterise=_make_arc4_unsigned_int_parameterise(max_bits=64),
)
GenericARC4BigUIntNType: typing.Final = GenericType(
    name=constants.CLS_ARC4_BIG_UINTN,
    parameterise=_make_arc4_unsigned_int_parameterise(),
)


ARC4ByteType: typing.Final[PyType] = ARC4UIntNType(
    generic=GenericARC4UIntNType,
    name=constants.CLS_ARC4_BYTE,
    wtype=wtypes.arc4_byte_type,
    bits=8,
).register()

ARC4UIntN_Aliases: typing.Final = immutabledict[int, ARC4UIntNType](
    {
        (_bits := 2**_exp): (GenericARC4UIntNType if _bits <= 64 else GenericARC4BigUIntNType)
        .parameterise([_bits], source_location=None)
        .register_alias(f"{constants.ARC4_PREFIX}UInt{_bits}")
        for _exp in range(3, 10)
    }
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


GenericTupleType: typing.Final = GenericType(
    name="builtins.tuple",
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


GenericArrayType: typing.Final = GenericType(
    name=constants.CLS_ARRAY,
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
    self: GenericType, args: TypeArgs, source_location: SourceLocation | None
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
        wtype=wtypes.WBoxMapProxy.from_key_and_content_type(content.wtype),
    )


GenericGlobalStateType: typing.Final = GenericType(
    name=constants.CLS_GLOBAL_STATE,
    parameterise=_make_storage_parameterise(wtypes.state_key),
)
GenericLocalStateType: typing.Final = GenericType(
    name=constants.CLS_LOCAL_STATE,
    parameterise=_make_storage_parameterise(wtypes.state_key),
)
GenericBoxType: typing.Final = GenericType(
    name=constants.CLS_BOX_PROXY,
    # TODO: FIXME
    # parameterise=_make_storage_parameterise(wtypes.box_key),
    parameterise=_make_storage_parameterise_todo_remove_me(wtypes.WBoxProxy.from_content_type),
)
BoxRefType: typing.Final = StorageProxyType(
    name=constants.CLS_BOX_REF_PROXY,
    content=BytesType,
    # wtype=wtypes.box_key,
    wtype=wtypes.box_ref_proxy_type,  # TODO: fixme
    generic=None,
).register()

GenericBoxMapType: typing.Final = GenericType(
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


class NamespaceType(PyType):
    generic: None = None
    metaclass: None = None

    @property
    def wtype(self) -> wtypes.WType:
        raise CodeError(f"{self} is a namespace type only and not usable at runtime")


def _make_op_namespace_types() -> Sequence[NamespaceType]:
    from itertools import chain

    from puya.awst_build.intrinsic_data import ENUM_CLASSES, NAMESPACE_CLASSES

    return [
        NamespaceType(name="".join((constants.ALGOPY_OP_PREFIX, cls_name))).register()
        for cls_name in chain(ENUM_CLASSES, NAMESPACE_CLASSES)
    ]


OpNamespaceTypes: typing.Final = _make_op_namespace_types()
