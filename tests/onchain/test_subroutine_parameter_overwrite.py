from tests.utils import decode_logs
from tests.utils.compile import compile_arc56_from_closure
from tests.utils.deployer import Deployer


def test_subroutine_parameter_overwrite(deployer: Deployer, optimization_level: int) -> None:
    def contract() -> None:
        from algopy import BaseContract, Bytes, log, op, subroutine

        class Exclaimer(BaseContract):
            def approval_program(self) -> bool:
                num_args = op.Txn.num_app_args
                assert num_args == 1, "expected one arg"
                msg = op.Txn.application_args(0)
                exclaimed = self.exclaim(msg)
                log(exclaimed)
                return True

            @subroutine
            def exclaim(self, value: Bytes) -> Bytes:
                value = value + b"!"
                return value

            def clear_state_program(self) -> bool:
                return True

    app_spec = compile_arc56_from_closure(contract, optimization_level=optimization_level)
    response = deployer.create_bare(app_spec, args=[b"whoop"])

    assert decode_logs(response.logs, "u") == ["whoop!"]
