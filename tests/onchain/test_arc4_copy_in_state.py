from tests.utils.compile import compile_arc56_from_closure
from tests.utils.deployer import Deployer


def test_arc4_copy_in_state(deployer: Deployer, optimization_level: int) -> None:
    def contract() -> None:
        from algopy import GlobalState, arc4

        class MyContract(arc4.ARC4Contract):
            def __init__(self) -> None:
                self.g = GlobalState(arc4.Address())

            @arc4.abimethod
            def okay(self) -> None:
                pass

    app_spec = compile_arc56_from_closure(contract, optimization_level=optimization_level)
    deployer.create(app_spec)
