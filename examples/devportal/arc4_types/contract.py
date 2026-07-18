import typing

from algopy import ARC4Contract, Bytes, GlobalState, String, UInt64, arc4, op, urange


class Arc4Types(ARC4Contract):
    # example: ARC4_UINT64
    @arc4.abimethod
    def add_arc4_uint64(self, a: arc4.UInt64, b: arc4.UInt64) -> arc4.UInt64:
        """
        Arithmetic operators are not defined directly on ARC-4 integer types
        because they are stored as fixed-width byte arrays in the AVM.
        Use `.as_uint64()` (or `.as_biguint()` for big integers) to obtain the
        native value, perform the math, then wrap the result back into the
        ARC-4 type for ABI compatibility.
        """
        c = a.as_uint64() + b.as_uint64()
        return arc4.UInt64(c)

    # example: ARC4_UINT64

    # example: ARC4_UINTN
    @arc4.abimethod
    def add_arc4_uint_n(
        self, a: arc4.UInt8, b: arc4.UInt16, c: arc4.UInt32, d: arc4.UInt64
    ) -> arc4.UInt64:
        """
        The encoding of ARC-4 integers uses fewer bytes for smaller bit widths.
        All `UIntN` variants up to 64 bits decode to the native `UInt64` via
        `.as_uint64()`.
        """
        assert a.bytes.length == 1, "UInt8 is encoded in 1 byte"
        assert b.bytes.length == 2, "UInt16 is encoded in 2 bytes"
        assert c.bytes.length == 4, "UInt32 is encoded in 4 bytes"
        assert d.bytes.length == 8, "UInt64 is encoded in 8 bytes"

        total = a.as_uint64() + b.as_uint64() + c.as_uint64() + d.as_uint64()
        return arc4.UInt64(total)

    # example: ARC4_UINTN

    # example: ARC4_BIGUINT
    @arc4.abimethod
    def add_arc4_biguint_n(
        self, a: arc4.UInt128, b: arc4.UInt256, c: arc4.UInt512
    ) -> arc4.UInt512:
        """
        Larger bit widths up to 512 bits are supported via `UIntN`.
        Their native representation is `BigUInt`, obtained via `.as_biguint()`.
        """
        assert a.bytes.length == 16, "UInt128 is encoded in 16 bytes"
        assert b.bytes.length == 32, "UInt256 is encoded in 32 bytes"
        assert c.bytes.length == 64, "UInt512 is encoded in 64 bytes"

        total = a.as_biguint() + b.as_biguint() + c.as_biguint()
        return arc4.UInt512(total)

    # example: ARC4_BIGUINT

    # example: ARC4_BYTES
    @arc4.abimethod
    def arc4_byte(self, a: arc4.Byte) -> arc4.Byte:
        """
        `arc4.Byte` is an alias for `arc4.UInt8`. As with other UIntN types,
        arithmetic goes through the native representation.
        """
        return arc4.Byte(a.as_uint64() + 1)

    # example: ARC4_BYTES

    # example: ARC4_ADDRESS
    @arc4.abimethod
    def arc4_address_balance(self, address: arc4.Address) -> UInt64:
        # The underlying 32 bytes of the address.
        _underlying_bytes = address.bytes

        # Decode into the native `Account` reference type.
        account = address.native
        return account.balance

    @arc4.abimethod
    def arc4_address_roundtrip(self, address: arc4.Address) -> arc4.Address:
        # `address.native` returns an `Account`, which is a reference type and
        # therefore can't be returned directly from an ABI method.
        # Wrap it back into `arc4.Address` for the return value.
        converted_address = arc4.Address(address.native)
        assert converted_address == address
        return converted_address

    # example: ARC4_ADDRESS


# example: ARC4_STATIC_ARRAY
AliasedStaticArray: typing.TypeAlias = arc4.StaticArray[arc4.UInt8, typing.Literal[1]]


class Arc4StaticArray(ARC4Contract):
    @arc4.abimethod
    def arc4_static_array(self) -> None:
        # A static array has a fixed, compile-time length.
        static_uint32_array = arc4.StaticArray(
            arc4.UInt32(1), arc4.UInt32(10), arc4.UInt32(2048), arc4.UInt32(128)
        )

        total = UInt64(0)
        for item in static_uint32_array:
            total += item.as_uint64()
        assert total == 1 + 10 + 2048 + 128

        # A type alias makes the element type and length explicit at the use site.
        aliased_static = AliasedStaticArray(arc4.UInt8(101))
        index = UInt64(0)
        assert (aliased_static[0].as_uint64() + aliased_static[index].as_uint64()) == 202

        aliased_static[0] = arc4.UInt8(202)
        assert aliased_static[0] == 202

        # Static arrays are fixed-size: `.pop()` or `.append(...)` would not compile.


# example: ARC4_STATIC_ARRAY


# example: ARC4_DYNAMIC_ARRAY
Goodbye: typing.TypeAlias = arc4.DynamicArray[arc4.String]


class Arc4DynamicArray(ARC4Contract):
    @arc4.abimethod
    def goodbye(self, name: arc4.String) -> Goodbye:
        return Goodbye(arc4.String("Good bye "), name)

    @arc4.abimethod
    def hello(self, name: arc4.String) -> String:
        """
        Dynamic arrays have variable size and capacity. They support
        `append`, `extend`, `pop`, and concatenation via `+`.
        """
        dynamic_string_array = arc4.DynamicArray[arc4.String](arc4.String("Hello "))

        extension = arc4.DynamicArray[arc4.String](name, arc4.String("!"))
        dynamic_string_array.extend(extension)

        copied = dynamic_string_array.copy()
        # `pop()` removes and returns the last element
        last = copied.pop()
        assert last == "!", "last element should be the exclamation mark"
        second_last = copied.pop()
        assert second_last == name, "second last element should be the name"
        copied.append(arc4.String("world!"))
        assert copied.length == 2, "copied is now ['Hello ', 'world!']"

        greeting = String()
        for x in dynamic_string_array:
            greeting += x.native
        return greeting

    # example: ARC4_DYNAMIC_ARRAY

    # example: ARC4_DYNAMIC_BYTES
    @arc4.abimethod
    def arc4_dynamic_bytes(self) -> arc4.DynamicBytes:
        """
        `arc4.DynamicBytes` is `arc4.DynamicArray[arc4.Byte]` with extra
        convenience: it can be constructed from a `bytes` literal and
        decoded to native `Bytes` via `.native`.
        """
        dynamic_bytes = arc4.DynamicBytes(b"\xff\xff\xff")

        # Unlike a generic `DynamicArray`, `DynamicBytes` exposes `.native`
        # so the whole sequence can be decoded in one step.
        native_dynamic_bytes = dynamic_bytes.native
        assert native_dynamic_bytes.length == 3

        dynamic_bytes[0] = arc4.Byte(0)
        dynamic_bytes.extend(arc4.DynamicBytes(b"\xaa\xbb\xcc"))
        _popped = dynamic_bytes.pop()
        dynamic_bytes.append(arc4.Byte(255))

        return dynamic_bytes

    # example: ARC4_DYNAMIC_BYTES


# example: ARC4_STRUCT
class Todo(arc4.Struct, kw_only=True):
    """
    `arc4.Struct` declares a named, ARC-4-encoded record type. Subclass options:
      - `kw_only=True` forces keyword construction, which keeps call sites
        readable when fields are added or reordered.
      - `frozen=True` (not used here) makes the struct immutable;
        mutations must go through `_replace(...)`.
    """

    task: arc4.String
    completed: arc4.Bool


Todos: typing.TypeAlias = arc4.DynamicArray[Todo]


class Arc4Struct(ARC4Contract):
    def __init__(self) -> None:
        self.todos = Todos()

    @arc4.abimethod
    def add_todo(self, task: arc4.String) -> Todos:
        todo = Todo(task=task, completed=arc4.Bool(False))
        self.todos.append(todo.copy())
        return self.todos

    @arc4.abimethod
    def complete_todo(self, task: arc4.String) -> None:
        for index in urange(self.todos.length):
            if self.todos[index].task == task:
                self.todos[index].completed = arc4.Bool(True)
                break

    @arc4.abimethod
    def return_todo(self, task: arc4.String) -> Todo:
        for index in urange(self.todos.length):
            if self.todos[index].task == task:
                return self.todos[index].copy()
        op.err("todo not found")


# example: ARC4_STRUCT


# example: ARC4_TUPLE
ContactInfo: typing.TypeAlias = arc4.Tuple[arc4.String, arc4.String, arc4.UInt64]


class Arc4Tuple(ARC4Contract):
    def __init__(self) -> None:
        self.contact_info = GlobalState(
            ContactInfo((arc4.String(""), arc4.String(""), arc4.UInt64(0)))
        )

    @arc4.abimethod
    def add_contact_info(self, contact: ContactInfo) -> UInt64:
        """An `arc4.Tuple` is a heterogeneous, ARC-4-encoded collection.
        `.native` unpacks it into a regular Python tuple of the element types."""
        name, email, phone = contact.native
        assert name.native == "Alice", "unexpected name"
        assert email.native == "alice@something.com", "unexpected email"
        assert phone == 555_555_555, "unexpected phone number"

        self.contact_info.value = contact
        return phone.as_uint64()

    @arc4.abimethod
    def return_contact(self) -> ContactInfo:
        return self.contact_info.value


# example: ARC4_TUPLE


# example: ARC4_ENCODE_DECODE
class Arc4Codec(ARC4Contract):
    """
    Demonstrates `arc4.encode` and `arc4.decode`, the general-purpose
    ARC-4 codec. Use these when you need to:
      * Build or parse ARC-4 bytes by hand (e.g. constructing event
        payloads, decoding bytes received off-chain).
      * Round-trip a value through bytes for hashing, signing, or storage.
    """

    @arc4.abimethod
    def encode_decode(self, value: UInt64) -> UInt64:
        """`arc4.encode(value)` returns the ARC-4 encoded bytes; passing
        the bytes plus a target type to `arc4.decode` reverses it."""
        encoded: Bytes = arc4.encode(value)
        assert encoded.length == 8, "UInt64 encodes to 8 big-endian bytes"

        decoded: UInt64 = arc4.decode(UInt64, encoded)
        assert decoded == value, "round-trip through bytes preserves the value"
        return decoded

    @arc4.abimethod
    def decode_unvalidated(self, raw: Bytes) -> arc4.UInt64:
        """
        `decode(..., validate=False)` skips the ARC-4 encoding check on the
        input bytes. Smaller bytecode, faster — but only safe when you
        already trust the source of the bytes (e.g. you wrote them in the
        same program). Defaults to `validate=True`.
        """
        return arc4.decode(arc4.UInt64, raw, validate=False)


# example: ARC4_ENCODE_DECODE
