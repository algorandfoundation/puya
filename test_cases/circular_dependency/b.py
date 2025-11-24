from algopy import Application, ARC4Contract, String, arc4

from test_cases.circular_dependency.a import A


class B(ARC4Contract):
    @arc4.abimethod()
    def ping(self) -> String:
        return String("ping")

    @arc4.abimethod
    def pong(self, a: Application) -> String:
        result, _txn = arc4.abi_call(A.pong, app_id=a)
        return result

    @arc4.abimethod
    def create_a(self, factory_id: Application) -> Application:
        from test_cases.circular_dependency.factory import Factory

        result, _txn = arc4.abi_call(Factory.deploy_a, app_id=factory_id)
        return result
