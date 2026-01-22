from tests.utils.compile import compile_arc56_from_closure
from tests.utils.deployer import Deployer


def test_ignored_value(deployer: Deployer, optimization_level: int) -> None:
    def contract() -> None:
        from algopy import Contract, subroutine

        class Silly(Contract):
            def approval_program(self) -> bool:
                True  # noqa: B018
                self.silly()
                return True

            @subroutine
            def silly(self) -> bool:
                True  # noqa: B018
                return True

            def clear_state_program(self) -> bool:
                return True

    app_spec = compile_arc56_from_closure(contract, optimization_level=optimization_level)
    deployer.create_bare(app_spec)
