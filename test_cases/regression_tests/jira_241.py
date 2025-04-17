from algopy import ARC4Contract, arc4


class Jira241(ARC4Contract):
    @arc4.abimethod(default_args={"wrong_size": False})
    def oh_no(self, wrong_size: bool) -> None:
        pass

    @arc4.abimethod(default_args={"wrong_size": True})
    def oh_yes(self, wrong_size: bool) -> None:
        pass
