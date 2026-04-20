from algopy import Contract, UInt64, logicsig, op


class ReplaceOpSelection(Contract):
    def approval_program(self) -> bool:
        assert op.replace(b"\x01" * 259, 256, b"abc") == b"\x01" * 256 + b"abc"
        return True

    def clear_state_program(self) -> bool:
        return True


class ExtractOpSelection(Contract):
    def approval_program(self) -> bool:
        # start > 255 forces extract3 (uint64 stack args) over extract (uint8 immediates)
        assert op.extract(b"\xab" * 260, 256, 3) == b"\xab\xab\xab"
        # length > 255 does the same
        assert op.extract(b"\xcd" * 300, 0, 300) == b"\xcd" * 300
        return True

    def clear_state_program(self) -> bool:
        return True


class SubstringOpSelection(Contract):
    def approval_program(self) -> bool:
        # end > 255 forces substring3 (uint64 stack args) over substring (uint8 immediates)
        assert op.substring(b"\xab" * 300, 0, 300) == b"\xab" * 300
        # start > 255 likewise
        assert op.substring(b"\xcd" * 260, 256, 259) == b"\xcd\xcd\xcd"
        return True

    def clear_state_program(self) -> bool:
        return True


class GaidOpSelection(Contract):
    def approval_program(self) -> UInt64:
        # T > 255 forces gaids (uint64 stack arg) over gaid (uint8 immediate).
        # Compile-only: runtime would fail since group indices are bounded by GroupIndex.
        return op.gaid(256)

    def clear_state_program(self) -> bool:
        return True


class GloadTOpSelection(Contract):
    def approval_program(self) -> UInt64:
        # T > 255, I <= 255 lets the optimizer downgrade gloadss -> gloads
        # (I as uint8 immediate, T on stack). At O0 it stays as gloadss.
        # Compile-only: runtime would fail since T is not a reachable group index.
        return op.gload_uint64(256, 0)

    def clear_state_program(self) -> bool:
        return True


class GloadIOpSelection(Contract):
    def approval_program(self) -> UInt64:
        # I > 255 must leave gloadss alone: no AVM variant has T as immediate
        # with I on the stack. Compile-only: runtime would fail since I is not
        # a reachable scratch slot.
        return op.gload_uint64(0, 256)

    def clear_state_program(self) -> bool:
        return True


class TxnArrayOpSelection(Contract):
    def approval_program(self) -> bool:
        # I > 255 forces txnas (uint64 stack arg) over txna (uint8 immediate).
        # Compile-only: runtime would fail since 256 is beyond the txn's ApplicationArgs array.
        assert op.Txn.application_args(256) != b""
        return True

    def clear_state_program(self) -> bool:
        return True


class GTxnOpSelection(Contract):
    def approval_program(self) -> UInt64:
        # T > 255 forces gtxns (uint64 stack arg) over gtxn (uint8 immediate).
        # Compile-only: runtime would fail since 256 is beyond the txn group.
        return op.GTxn.fee(256)

    def clear_state_program(self) -> bool:
        return True


class GTxnArrayGroupOpSelection(Contract):
    def approval_program(self) -> bool:
        # T > 255, I <= 255 forces gtxnsas (both on stack) -> gtxnsa (I immediate, T on stack).
        # Compile-only: runtime would fail since 256 is beyond the txn group.
        assert op.GTxn.application_args(256, 0) != b""
        return True

    def clear_state_program(self) -> bool:
        return True


class GTxnArrayIndexOpSelection(Contract):
    def approval_program(self) -> bool:
        # T <= 255, I > 255 forces gtxnsas -> gtxnas (T immediate, I on stack).
        # Compile-only: runtime would fail since 256 is beyond ApplicationArgs.
        assert op.GTxn.application_args(0, 256) != b""
        return True

    def clear_state_program(self) -> bool:
        return True


@logicsig
def arg_op_selection() -> bool:
    # N > 255 forces args (uint64 stack arg) over arg (uint8 immediate)
    assert op.arg(256) != b""
    return True
