import abc
import typing

from algopy import Application, ARC4Contract, String, arc4, subroutine

if typing.TYPE_CHECKING:
    from test_cases.circular_dependency.a import MyInnerStruct


# TODO: allow this to work
# class MyStruct(arc4.Struct):
#     value: arc4.UInt64
#     inner: "MyInnerStruct"


class PingPongBase(ARC4Contract, abc.ABC):
    @abc.abstractmethod
    @arc4.abimethod
    def name(self) -> String: ...


class B(PingPongBase):
    @typing.override
    @arc4.abimethod
    def name(self) -> String:
        return String("B")

    @arc4.abimethod()
    def ping(self) -> String:
        return String("ping")

    @arc4.abimethod
    def pong(self, a: Application) -> String:
        from test_cases.circular_dependency.a import A

        result, _txn = arc4.abi_call(A.pong, app_id=a)
        return result

    @arc4.abimethod
    def create_a(self, factory_id: Application) -> Application:
        from test_cases.circular_dependency.factory import Factory

        result, _txn = arc4.abi_call(Factory.deploy_a, app_id=factory_id)
        return result

    # TODO: allow this to work
    # @arc4.abimethod
    # def check_inner(self, s: "MyInnerStruct") -> None:
    #     check_inner(s)


@subroutine
def check_inner(s: "MyInnerStruct") -> None:
    assert s.value == 42
