from puyapy_mocks._ctx import active_ctx
from puyapy_mocks._primatives import (
    Bytes,
    UInt64,
)


def btoi(a: Bytes | bytes, /) -> UInt64:
    if isinstance(a, Bytes):
        a = bytes(a)
    return UInt64(int.from_bytes(a))


def itob(a: int | UInt64, /) -> Bytes:
    if isinstance(a, UInt64):
        a = int(a)
    return Bytes(int.to_bytes(a, 8))


# TODO: NC - Come back to this and see if we can simplify
class classproperty(property):  # noqa: N801
    pass


class StaticProperty(type):
    def __new__(cls, name, bases, props):  # type: ignore[no-untyped-def]  # noqa: ANN204, ANN001
        class_properties = {}
        to_remove = {}
        for key, value in props.items():
            if isinstance(value, (classproperty)):
                class_properties[key] = value
                if isinstance(value, classproperty):
                    to_remove[key] = value

        for key in to_remove:
            props.pop(key)

        hoist_meta = type("HoistMeta", (type,), class_properties)
        return hoist_meta(name, bases, props)


class Txn(metaclass=StaticProperty):
    @classmethod
    def application_args(cls, index: int) -> bytes:
        return active_ctx().get_arg(index)

    @classproperty
    def num_app_args(self) -> int:
        return len(active_ctx()._args)  # noqa: SLF001
