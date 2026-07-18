from algopy import Application, ARC4Contract, TemplateVar, UInt64, arc4


# example: APP_REFERENCE_EXAMPLE
class Counter(ARC4Contract):
    """A trivial callee whose state is incremented by inner app calls."""

    def __init__(self) -> None:
        self.counter = UInt64(0)

    @arc4.abimethod
    def increment(self) -> UInt64:
        self.counter += 1
        return self.counter


class ReferenceApp(ARC4Contract):
    """
    Demonstrates referencing another application by id and invoking one of its
    methods via `arc4.abi_call`. The referenced app must be present in the
    transaction's reference arrays at call time (the AlgoKit client typically
    handles this automatically).
    """

    @arc4.abimethod
    def increment_via_inner(self) -> UInt64:
        """Call into a well-known `Counter` application, baked into the
        program when it is compiled/deployed (`TMPL_KNOWN_APP`)."""
        app = TemplateVar[Application]("KNOWN_APP")
        # fee=0 means the outer transaction's fee must also cover the inner call
        counter_result, _txn = arc4.abi_call(Counter.increment, fee=0, app_id=app)
        return counter_result

    @arc4.abimethod
    def increment_via_inner_with_arg(self, app: Application) -> UInt64:
        """Same call, but the target app is supplied by the caller."""
        counter_result, _txn = arc4.abi_call(Counter.increment, fee=0, app_id=app)
        return counter_result


# example: APP_REFERENCE_EXAMPLE
