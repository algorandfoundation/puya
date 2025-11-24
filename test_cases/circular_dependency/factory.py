from algopy import Application, ARC4Contract, arc4


class Factory(ARC4Contract):
    @arc4.abimethod
    def deploy_a(self) -> Application:
        from test_cases.circular_dependency.a import A

        txn = arc4.arc4_create(A)
        return txn.created_app

    @arc4.abimethod
    def deploy_b(self) -> Application:
        from test_cases.circular_dependency.b import B

        txn = arc4.arc4_create(B)
        return txn.created_app
