from algopy import logicsig


@logicsig(name="always_allow")
def some_sig() -> bool:
    return True
