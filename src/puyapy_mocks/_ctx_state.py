import attrs


@attrs.define
class ExecutionContextState:
    args: list[bytes] = attrs.field(factory=list)
    logs: list[bytes] = attrs.field(factory=list)
    balances: dict[str, dict[int, int]] = attrs.field(factory=dict)

    def adjust_balance(self, address: str, asset_id: int, amount: int) -> None:
        if address not in self.balances:
            self.balances[address] = {}
        if asset_id not in self.balances[address]:
            self.balances[address][asset_id] = 0
        self.balances[address][asset_id] += amount

    def get_balance(self, address: str, asset_id: int) -> int:
        try:
            return self.balances[address][asset_id]
        except KeyError:
            return 0


_ctx: dict[str, ExecutionContextState | None] = {"active": None}


def active_ctx() -> ExecutionContextState:
    active = _ctx["active"]
    if active is None:
        raise Exception("No context available, begin a context with execution_ctx")
    return active
