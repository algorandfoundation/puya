import typing

from algopy import (
    ARC4Contract,
    Box,
    BoxMap,
    BoxRef,
    Bytes,
    GlobalState,
    LocalState,
    String,
    TemplateVar,
    UInt64,
    arc4,
    subroutine,
)


class SharedStruct(arc4.Struct):
    """This struct is shared"""

    foo: arc4.DynamicBytes
    bar: arc4.UInt8


class EventOnly(arc4.Struct):
    """This struct is only used in an event"""

    x: arc4.UInt64
    y: arc4.UInt64


class TopLevelStruct(arc4.Struct):
    a: arc4.UInt64
    b: arc4.String
    shared: SharedStruct


class StateStruct(arc4.Struct):
    a: arc4.UInt64
    b: arc4.String


@subroutine
def constant_method() -> UInt64:
    return UInt64(42)


@subroutine
def echo_number(x: UInt64) -> UInt64:
    return x


class Contract(ARC4Contract):
    """Contract docstring"""

    def __init__(self) -> None:
        self.g_struct = GlobalState(StateStruct)
        self.g_uint64 = GlobalState(UInt64, key=b"gu")
        self.g_address = GlobalState(arc4.Address, key=b"ga")

        self.l_struct = LocalState(StateStruct)
        self.l_uint64 = LocalState(UInt64, key=b"lu")
        self.l_address = LocalState(arc4.Address, key=b"la")

        self.b_struct = Box(StateStruct)
        self.b_uint64 = Box(UInt64, key=b"bu")
        self.b_address = Box(arc4.Address, key=b"ba")

        self.box_map_struct = BoxMap(StateStruct, SharedStruct)
        self.box_map_uint64 = BoxMap(UInt64, SharedStruct, key_prefix=b"bmu")
        self.box_map_address = BoxMap(arc4.Address, SharedStruct, key_prefix=b"bma")

        self.box_ref = BoxRef()
        self.box_ref2 = BoxRef(key=b"br")

    @arc4.baremethod(create="allow", allow_actions=["NoOp", "OptIn"])
    def bare_create(self) -> None:
        pass

    @arc4.abimethod(create="allow", allow_actions=["NoOp", "OptIn"])
    def create(self) -> None:
        """Method docstring"""

    @arc4.baremethod(create="require", allow_actions=["DeleteApplication"])
    def transient(self) -> None:
        pass

    @arc4.abimethod()
    def struct_arg(self, arg: TopLevelStruct, shared: SharedStruct) -> UInt64:
        """Method docstring2"""
        assert arg.shared == shared, "this might error"
        return UInt64(42)

    @arc4.abimethod(readonly=True)
    def struct_return(self, arg: TopLevelStruct) -> SharedStruct:
        assert arg.shared == echo(arg.shared), "this won't error"
        return arg.shared

    @arc4.abimethod(name="emits_error", readonly=True)
    def errors(self, arg: TopLevelStruct) -> None:
        assert arg.a.bytes == arc4.UInt8(0).bytes, "this will error"

    @arc4.abimethod()
    def emitter(self) -> None:
        arc4.emit(SharedStruct(foo=arc4.DynamicBytes(b"hello1"), bar=arc4.UInt8(42)))

        arc4.emit(
            "Anonymous",
            String("hello"),
            SharedStruct(foo=arc4.DynamicBytes(b"hello2"), bar=arc4.UInt8(42)),
        )

    @arc4.abimethod()
    def conditional_emit(self, should_emit: bool) -> None:
        if should_emit:
            arc4.emit(
                "Anonymous2",
                EventOnly(arc4.UInt64(42), arc4.UInt64(43)),
                SharedStruct(foo=arc4.DynamicBytes(b"hello3"), bar=arc4.UInt8(42)),
            )

    @arc4.abimethod()
    def template_value(self) -> tuple[SharedStruct, UInt64, String, arc4.UInt8]:
        return (
            TemplateVar[SharedStruct]("STRUCT"),
            TemplateVar[UInt64]("AVM_UINT64"),
            TemplateVar[String]("AVM_STRING"),
            TemplateVar[arc4.UInt8]("ARC4_UINT8"),
        )

    @arc4.abimethod(
        default_args={
            "a": arc4.UInt64(123),
            "c": Bytes(b"123"),
            "b": UInt64(234),
            "d": EventOnly(x=arc4.UInt64(1), y=arc4.UInt64(2)),
            "e": (UInt64(42), String("on the edge")),
            "f": arc4.StaticArray(arc4.String("hi"), arc4.String("there!")),
            "g": arc4.DynamicArray(arc4.String("one"), arc4.String("two")),
            "h": constant_method(),
            "i": echo_number(UInt64(1234)),
        }
    )
    def with_constant_defaults(
        self,
        a: arc4.UInt64,
        b: UInt64,
        c: Bytes,
        d: EventOnly,
        e: tuple[UInt64, String],
        f: arc4.StaticArray[arc4.String, typing.Literal[2]],
        g: arc4.DynamicArray[arc4.String],
        h: UInt64,
        i: UInt64,
    ) -> None:
        assert a
        assert b
        assert c
        assert d.x or d.y
        assert e[0] or e[1]
        assert f[0] == "hi"
        assert g.length == 2
        assert h == 42
        assert i == 1234


@subroutine
def echo(s: SharedStruct) -> SharedStruct:
    return s
