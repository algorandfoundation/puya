import typing

from algopy import Application, String, arc4

from test_cases.circular_dependency.b import B, PingPongBase


class MyInnerStruct(arc4.Struct):
    value: arc4.UInt64


class A(PingPongBase):
    @typing.override
    @arc4.abimethod
    def name(self) -> String:
        return String("A")

    @arc4.abimethod
    def ping(self, b: Application) -> String:
        result, _txn = arc4.abi_call(B.ping, app_id=b)
        return result

    @arc4.abimethod()
    def pong(self) -> String:
        return String("pong")

    @arc4.abimethod
    def create_b(self, factory_id: Application) -> Application:
        from test_cases.circular_dependency.factory import Factory

        result, _txn = arc4.abi_call(Factory.deploy_b, app_id=factory_id)
        return result
