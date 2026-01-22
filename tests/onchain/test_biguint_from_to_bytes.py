from tests.utils import decode_logs
from tests.utils.compile import compile_arc56_from_closure
from tests.utils.deployer import Deployer


def test_biguint_from_to_bytes(deployer: Deployer, optimization_level: int) -> None:
    def contract() -> None:
        from algopy import BigUInt, Contract, log, op

        class BigUIntByteTests(Contract):
            def approval_program(self) -> bool:
                arg = op.Txn.application_args(0)
                big_uint = BigUInt.from_bytes(arg)
                big_uint += 1
                log(big_uint.bytes)
                return True

            def clear_state_program(self) -> bool:
                return True

    app_spec = compile_arc56_from_closure(contract, optimization_level=optimization_level)
    result = deployer.create_bare(app_spec, args=[122])
    assert decode_logs(result.logs, "i") == [123]
