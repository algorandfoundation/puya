import itertools
import typing
from collections.abc import Mapping

import attrs

from puya.ir import (
    encodings,
    models,
    types_ as types,
)
from puya.ir.avm_ops import AVMOp
from puya.ir.types_ import AVMBytesEncoding, PrimitiveIRType
from puya.utils import biguint_bytes_eval, lazy_setdefault

VN: typing.TypeAlias = int


@attrs.frozen(kw_only=True)
class ProviderKey:
    """Base class for canonical ValueProvider keys."""


@attrs.frozen(kw_only=True)
class IndexVN:
    """Tagged index for aggregate ops — distinguishes static int indices from dynamic VNs."""

    kind: typing.Literal["static", "value"]
    index: int


@attrs.frozen(kw_only=True)
class IntrinsicKey(ProviderKey):
    op: AVMOp
    immediates: tuple[str | int, ...]
    arg_vns: tuple[VN, ...]


@attrs.frozen(kw_only=True)
class ExtractKey(ProviderKey):
    base_vn: VN
    base_type: types.EncodedType  # important if there's aliasing
    index_vns: tuple[IndexVN, ...]
    check_bounds: bool


@attrs.frozen(kw_only=True)
class ReplaceKey(ProviderKey):
    base_vn: VN
    base_type: types.EncodedType
    index_vns: tuple[IndexVN, ...]
    value_vn: VN


@attrs.frozen(kw_only=True)
class ArrayLengthKey(ProviderKey):
    base_vn: VN
    base_type: types.IRType


@attrs.frozen(kw_only=True)
class ArrayPopKey(ProviderKey):
    base_vn: VN
    base_type: types.EncodedType


@attrs.frozen(kw_only=True)
class ArrayConcatKey(ProviderKey):
    base_vn: VN
    base_type: types.EncodedType
    items_vn: VN
    item_encoding: encodings.Encoding
    # num_items: redundant given the other fields


@attrs.frozen(kw_only=True)
class EncodeKey(ProviderKey):
    encoding: encodings.Encoding
    value_vns: tuple[VN, ...]
    values_type: types.IRType | types.TupleIRType


@attrs.frozen(kw_only=True)
class DecodeKey(ProviderKey):
    encoding: encodings.Encoding
    value_vn: VN
    ir_type: types.IRType | types.TupleIRType


@attrs.frozen(kw_only=True)
class CallSubKey(ProviderKey):
    target_id: str
    arg_vns: tuple[VN, ...]


@attrs.frozen(kw_only=True)
class ConstKey:
    """Base class for canonical constant keys."""


@attrs.frozen(kw_only=True)
class UInt64ConstKey(ConstKey):
    value: int
    ir_type: typing.Literal[PrimitiveIRType.uint64, PrimitiveIRType.bool] = attrs.field(
        default=PrimitiveIRType.uint64, eq=False
    )


@attrs.frozen(kw_only=True)
class BytesConstKey(ConstKey):
    value: bytes
    # encoding is metadata only — same bytes with different encodings get the same VN.
    encoding: AVMBytesEncoding = attrs.field(default=AVMBytesEncoding.unknown, eq=False)

    @property
    def as_biguint(self) -> int | None:
        if len(self.value) > 64:
            return None
        return int.from_bytes(self.value, "big", signed=False)


@attrs.frozen(kw_only=True)
class TemplateVarKey(ConstKey):
    name: str


# When equal bytes with different encodings share a VN, the more-informative encoding
# wins (enum order: unknown < base16 < base32 < base64 < utf8).
ENCODING_PREF: typing.Final[Mapping[AVMBytesEncoding, int]] = {
    enc: i for i, enc in enumerate(AVMBytesEncoding)
}

if typing.TYPE_CHECKING:
    IntCounter = itertools.count[int]
else:
    IntCounter = itertools.count


@attrs.define(init=False)
class GVNTables:
    """Value-numbering state for one `number_values` call (Briggs et al. unified
    hash table). `_vn_counter` and `_provider_key_to_vns` are monotonic across
    optimistic iterations; `register_vn` is overwritten as VNs refine."""

    _vn_counter: IntCounter = attrs.field(factory=itertools.count)
    register_vn: dict[models.Register, VN] = attrs.field(factory=dict)
    _provider_key_to_vns: dict[ProviderKey, tuple[VN, ...]] = attrs.field(factory=dict)
    _const_vn: dict[ConstKey, VN] = attrs.field(factory=dict)
    vn_definition: dict[VN, ConstKey | ProviderKey] = attrs.field(factory=dict)
    # Per-phi stable VN, pinned once so it survives re-iteration.
    _phi_stable_vn: dict[models.Phi, VN] = attrs.field(factory=dict)
    # VNs for non-structural providers, keyed by id(vp) for cross-iteration stability.
    _identity_vns: dict[int, tuple[VN, ...]] = attrs.field(factory=dict)

    def __init__(self, subroutine: models.Subroutine) -> None:
        self.__attrs_init__()
        for param in subroutine.parameters:
            self.assign_register_fresh_vn(param)

    def next_vn(self) -> VN:
        return next(self._vn_counter)

    def set_register_vn(self, reg: models.Register, vn: VN) -> None:
        self.register_vn[reg] = vn

    def assign_register_fresh_vn(self, reg: models.Register) -> VN:
        vn = self.next_vn()
        self.set_register_vn(reg, vn)
        return vn

    def stable_phi_vn(self, phi: models.Phi) -> VN:
        """Persistent VN for a non-redundant phi"""
        # same VN every iteration, so the register partition converges,
        # even when the phi's args never agree.
        return lazy_setdefault(self._phi_stable_vn, phi, lambda _: self.next_vn())

    def fresh_vns(self, vp: models.ValueProvider) -> tuple[VN, ...]:
        """VNs for a provider that can't be numbered structurally."""
        # Memoised by id(vp) so the same op instance is stable across re-walk.
        return lazy_setdefault(
            self._identity_vns, id(vp), lambda _: tuple(self.next_vn() for _ in vp.types)
        )

    def lookup_or_assign_vp(
        self, key: ProviderKey, source: models.ValueProvider
    ) -> tuple[VN, ...]:
        try:
            return self._provider_key_to_vns[key]
        except KeyError:
            pass
        # Mint VNs directly, not via fresh_vns: stability comes from the key cache
        # (same key -> same VN next iteration)
        vns = tuple(self.next_vn() for _ in source.types)
        self._provider_key_to_vns[key] = vns
        if len(vns) == 1:
            (vn,) = vns
            self.vn_definition[vn] = key
        return vns

    def lookup_or_assign_const(self, key: ConstKey) -> tuple[VN, ...]:
        vn = lazy_setdefault(self._const_vn, key, lambda _: self.next_vn())
        if isinstance(key, BytesConstKey):
            prior = self.vn_definition.get(vn)
            if prior is not None:
                assert isinstance(prior, BytesConstKey)
                if ENCODING_PREF[prior.encoding] > ENCODING_PREF[key.encoding]:
                    key = prior
        self.vn_definition[vn] = key
        return (vn,)

    def const_uint64(self, value: int) -> tuple[VN, ...]:
        key = UInt64ConstKey(value=value)
        return self.lookup_or_assign_const(key)

    def const_bool(self, value: int) -> tuple[VN, ...]:
        bool_value = 1 if value else 0
        key = UInt64ConstKey(value=bool_value, ir_type=PrimitiveIRType.bool)
        return self.lookup_or_assign_const(key)

    def const_bytes(self, value: bytes, encoding: AVMBytesEncoding) -> tuple[VN, ...]:
        key = BytesConstKey(value=value, encoding=encoding)
        return self.lookup_or_assign_const(key)

    def const_biguint(self, value: int) -> tuple[VN, ...]:
        evald = biguint_bytes_eval(value)
        return self.const_bytes(evald, AVMBytesEncoding.base16)
