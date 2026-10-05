import typing

from algopy import (
    Application,
    ARC4Contract,
    Box,
    Bytes,
    Global,
    Local,
    Remote,
    UInt64,
    arc4,
    subroutine,
)


class Counters(arc4.Struct):
    a: arc4.UInt64
    b: arc4.UInt64


class BigStruct(arc4.Struct):
    # deliberately larger than a single stack value, but still within a single box op
    values: arc4.StaticArray[arc4.UInt64, typing.Literal[400]]


class RemoteBoxContract(ARC4Contract, avm_version=13):
    def __init__(self) -> None:
        # a local box, to check the two locations coexist on the one Box type
        self.local_box = Box(UInt64, key=b"local")

    @arc4.abimethod
    def local_app_is_current_app(self) -> bool:
        return self.local_box.app == Global.current_application_id

    @arc4.abimethod
    def explicit_location(self, app: Application) -> UInt64:
        local: Box[UInt64, Local] = Box(UInt64, key=b"counter")
        remote: Box[UInt64, Remote] = Box.remote(UInt64, app=app, key=b"counter")
        return local.value + remote.value

    @arc4.abimethod
    def read(self, app: Application) -> UInt64:
        box = Box.remote(UInt64, app=app, key=b"counter")
        return box.value

    @arc4.abimethod
    def read_with_default(self, app: Application) -> UInt64:
        box = Box.remote(UInt64, app=app, key=b"counter")
        return box.get(default=UInt64(42))

    @arc4.abimethod
    def maybe(self, app: Application) -> tuple[UInt64, bool]:
        box = Box.remote(UInt64, app=app, key=b"counter")
        return box.maybe()

    @arc4.abimethod
    def exists(self, app: Application) -> bool:
        box = Box.remote(UInt64, app=app, key=b"counter")
        return bool(box)

    @arc4.abimethod
    def length(self, app: Application) -> UInt64:
        box = Box.remote(Bytes, app=app, key=b"blob")
        return box.length

    @arc4.abimethod
    def write(self, app: Application, value: UInt64) -> None:
        box = Box.remote(UInt64, app=app, key=b"counter")
        box.value = value

    @arc4.abimethod
    def delete(self, app: Application) -> None:
        box = Box.remote(UInt64, app=app, key=b"counter")
        del box.value

    @arc4.abimethod
    def create_and_splice(self, app: Application, value: Bytes) -> Bytes:
        box = Box.remote(Bytes, app=app, key=b"blob")
        assert box.create(size=32), "box should not already exist"
        box.replace(0, value)
        box.splice(0, 4, value)
        box.resize(64)
        return box.extract(0, 8)

    @arc4.abimethod
    def struct_member_write(self, app: Application, value: arc4.UInt64) -> None:
        box = Box.remote(Counters, app=app, key=b"counters")
        box.value.a = value
        box.value.b = value

    @arc4.abimethod
    def big_read(self, app: Application, index: UInt64) -> arc4.UInt64:
        # exercises the BoxRead path rather than the app_box_get path
        box = Box.remote(BigStruct, app=app, key=b"big")
        return box.value.values[index]

    @arc4.abimethod
    def big_write(self, app: Application, index: UInt64, value: arc4.UInt64) -> None:
        box = Box.remote(BigStruct, app=app, key=b"big")
        box.value.values[index] = value

    @arc4.abimethod
    def key_and_app(self, app: Application) -> tuple[Bytes, UInt64]:
        box = Box.remote(UInt64, app=app, key=b"counter")
        return box.key, box.app.id

    @arc4.abimethod
    def same_key_as_local(self, app: Application, value: arc4.UInt64) -> None:
        # a local box and a remote box can share a key, so a value read from one must never be
        # written back to the other - the in-place box update optimisation rewrites a whole box
        # write into box_extract/box_replace, which only ever address the current application
        local = Box(Counters, key=b"counters")
        remote = Box.remote(Counters, app=app, key=b"counters")
        updated = local.value.copy()
        updated.a = value
        remote.value = updated.copy()

    @arc4.abimethod
    def same_key_as_local_array(self, app: Application, value: arc4.UInt64) -> None:
        # as above, for the array concat/pop variants of the same optimisation
        local = Box(arc4.DynamicArray[arc4.UInt64], key=b"items")
        remote = Box.remote(arc4.DynamicArray[arc4.UInt64], app=app, key=b"items")
        updated = local.value.copy()
        updated.append(value)
        remote.value = updated.copy()

    @arc4.abimethod
    def passed_around(self, app: Application) -> UInt64:
        # the proxy survives a round trip through a local variable and a subroutine
        box = Box.remote(UInt64, app=app, key=b"counter")
        return _sum_twice(box)


@subroutine
def _sum_twice(box: Box[UInt64, Remote]) -> UInt64:
    return box.value + box.value
