from tests.utils.compile import compile_arc56_from_closure
from tests.utils.deployer import Deployer


def test_arc4_tuple_element_mutation(deployer: Deployer, optimization_level: int) -> None:
    def contract() -> None:
        from algopy import Contract, arc4

        class MyContract(Contract):
            def approval_program(self) -> bool:
                t = arc4.Tuple((arc4.UInt64(1), arc4.DynamicBytes(b"abc")))
                assert t[1].bytes[2:] == b"abc", "initial value"
                t[1].extend(arc4.DynamicBytes(b"def"))
                assert t[1].bytes[2:] == b"abcdef", "updated value"
                return True

            def clear_state_program(self) -> bool:
                return True

    app_spec = compile_arc56_from_closure(contract, optimization_level=optimization_level)
    deployer.create_bare(app_spec)
