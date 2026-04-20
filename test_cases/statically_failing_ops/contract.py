from algopy import Bytes, Contract, Global, UInt64, log, op


class StaticallyFailingOps(Contract):
    def approval_program(self) -> bool:
        # arithmetic overflow / underflow / div-zero / 0**0 / exp-overflow
        log(op.itob(UInt64(2**64 - 1) + 1))
        log(op.itob(UInt64(2**32) * UInt64(2**32)))
        log(op.itob(UInt64(1) - UInt64(2)))
        log(op.itob(UInt64(5) // UInt64(0)))
        log(op.itob(UInt64(5) % UInt64(0)))
        log(op.itob(UInt64(0) ** UInt64(0)))
        log(op.itob(UInt64(2) ** UInt64(64)))

        # shl / shr
        log(op.itob(op.shl(UInt64(1), 64)))
        log(op.itob(op.shr(UInt64(1), 64)))

        # btoi (len > 8) / bzero (len > 4096)
        log(op.itob(op.btoi(Bytes(b"123456789"))))
        log(op.bzero(5000))

        # extract — immediates form (S<256, L<256): L>0 OOB and L==0 with S>len
        log(op.extract(Bytes(b"ab"), 0, 5))
        log(op.extract(Bytes(b"ab"), 5, 0))
        # extract3 — stack-args form (UInt64(...) forces stack arg; S>255 prevents stack→imm)
        start = UInt64(300)
        log(op.extract(Bytes(b"ab"), start, UInt64(5)))

        # substring — immediates form: E<S and E>len
        log(op.substring(Bytes(b"ab"), 5, 1))
        log(op.substring(Bytes(b"ab"), 0, 5))
        # substring3 — stack form
        sub_start = UInt64(300)
        log(op.substring(Bytes(b"ab"), sub_start, UInt64(500)))

        # replace2 — imm form, and replace3 — stack form
        log(op.replace(Bytes(b""), 0, Bytes(b"abc")))
        rep_start = UInt64(300)
        log(op.replace(Bytes(b""), rep_start, Bytes(b"abc")))

        # extract_uint{16,32,64} OOB
        log(op.itob(op.extract_uint16(Bytes(b"a"), 0)))
        log(op.itob(op.extract_uint32(Bytes(b"abc"), 0)))
        log(op.itob(op.extract_uint64(Bytes(b"abcdefg"), 0)))

        # getbit / setbit — uint64 and bytes variants
        log(op.itob(UInt64(op.getbit(UInt64(0), 64))))
        log(op.itob(UInt64(op.getbit(Bytes(b"a"), 8))))
        log(op.itob(op.setbit_uint64(UInt64(0), 64, True)))
        log(op.setbit_bytes(Bytes(b"a"), 8, True))

        # getbyte / setbyte
        log(op.itob(op.getbyte(Bytes(b"a"), 1)))
        log(op.setbyte(Bytes(b"a"), 1, 0))

        # helper-None coverage: runtime-variable indices so start/length aren't const
        r = Global.round
        log(op.extract(Bytes(b"ab"), r, UInt64(0)))
        log(op.substring(Bytes(b"ab"), r, r))
        log(op.replace(Bytes(b""), r, Bytes(b"abc")))

        return True

    def clear_state_program(self) -> bool:
        return True
