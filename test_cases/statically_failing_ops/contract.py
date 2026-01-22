from algopy import BigUInt, Bytes, Contract, Global, Txn, UInt64, log, op, subroutine


class StaticallyFailingOps(Contract, scratch_slots=(0,)):
    def approval_program(self) -> bool:
        runtime_bytes = Txn.application_args(0)
        runtime_uint64 = Global.round
        longest = Bytes(b" " * 4096)
        biggest = UInt64(2**64 - 1)

        # arithmetic overflow / underflow / div-zero / 0**0 / exp-overflow
        log(biggest + 1)
        log(biggest * 2)
        log(UInt64(0) - 1)
        log(runtime_uint64 // 0)
        log(runtime_uint64 % 0)
        log(UInt64(0) ** 0)
        log(UInt64(2) ** 64)

        # biguint sub underflow (folder declines to fold to negative result)
        log(BigUInt(0) - 1)
        # biguint oversized constant operand (folded sum > 512 bits, consumed by
        # non-folding op with a runtime operand)
        huge = BigUInt(2**512 - 1) + 1
        one_big = runtime_biguint()
        log(one_big + huge)
        # biguint div / mod by constant zero
        log(one_big // 0)
        log(one_big % 0)
        # biguint operand as oversized BytesConstant (reinterpreted via from_bytes)
        log(BigUInt.from_bytes(b"\xff" * 65) + BigUInt.from_bytes(runtime_bytes))
        # biguint sub underflow with BytesConstant operands (reinterpreted)
        log(BigUInt.from_bytes(b"\x00") - BigUInt.from_bytes(b"\x01"))
        log(one_big // BigUInt.from_bytes(b""))
        log(one_big % BigUInt.from_bytes(b""))

        # shl / shr
        log(op.shl(1, 64))
        log(op.shr(1, 64))

        # btoi (len > 8) / bzero (len > 4096)
        log(op.btoi(b"123456789"))
        log(op.bzero(5000))

        # extract — immediates form (S<256, L<256): L>0 OOB and L==0 with S>len
        log(op.extract(b"ab", 0, 5))
        log(op.extract(b"ab", 5, 0))
        # extract3 — S>255 prevents stack→imm
        log(op.extract(b"ab", 300, 5))

        # substring — immediates form: E>len
        # note: don't test E<S, this will cause compilation failure
        log(op.substring(b"ab", 0, 5))
        # substring3 — stack form (E>len, and E<S)
        log(op.substring(b"ab", 300, 500))
        log(op.substring(longest, 500, 0))
        # substring3 — runtime bytes with constant end > MAX_BYTES_LENGTH

        log(op.substring(runtime_bytes, 0, 5000))
        # substring3 — runtime start, constant end > MAX_BYTES_LENGTH (hits fallback)
        log(op.substring(runtime_bytes, runtime_uint64, 5000))

        # replace2 — imm form, and replace3 — stack form
        log(op.replace(b"", 0, b"abc"))
        log(op.replace(b"", 300, b"abc"))

        # extract_uint{16,32,64} OOB
        log(op.extract_uint16(b"a", 0))
        log(op.extract_uint32(b"abc", 0))
        log(op.extract_uint64(b"abcdefg", 0))

        # getbit / setbit — constant-bytes, uint64, and runtime-bytes variants
        log(op.getbit(0, 64))
        log(op.getbit(b"a", 8))
        log(op.getbit(runtime_bytes, 8 * 4096))
        log(op.setbit_uint64(0, 64, True))
        log(op.setbit_bytes(b"a", 8, True))
        log(op.setbit_bytes(runtime_bytes, 8 * 4096, True))

        # getbyte / setbyte — constant-bytes and runtime-bytes variants
        log(op.getbyte(b"a", 1))
        log(op.getbyte(runtime_bytes, 4096))
        log(op.setbyte(b"a", 1, 0))
        log(op.setbyte(runtime_bytes, 4096, 0))

        # helper-None coverage: runtime-variable indices so start/length aren't const
        log(op.extract(b"ab", runtime_uint64, 0))
        log(op.substring(b"ab", runtime_uint64, runtime_uint64))
        log(op.replace(b"", runtime_uint64, b"abc"))

        # concat
        log(longest + b"toobig")

        # scratch slot id > 255 (loads / stores / gloadss)
        op.Scratch.store(256, 0)
        log(op.Scratch.load_uint64(256))
        log(op.gload_uint64(0, 256))

        # box_extract length > MAX_BYTES_LENGTH
        log(op.Box.extract(b"k", 0, 5000))

        # box op constants exceeding maximum box size (32768)
        # box_create length > MAX_BOX_BYTES_LENGTH
        log(op.Box.create(b"k", 32769))
        # box_extract start > MAX_BOX_BYTES_LENGTH
        log(op.Box.extract(b"k", 32769, 0))
        # box_extract start + length > MAX_BOX_BYTES_LENGTH (length within stack limit)
        log(op.Box.extract(b"k", 32000, 1000))
        # box_replace start > MAX_BOX_BYTES_LENGTH
        op.Box.replace(b"k", 32769, b"")
        # box_replace start + len(replacement) > MAX_BOX_BYTES_LENGTH
        op.Box.replace(b"k", 32700, b"x" * 100)
        # box_resize new length > MAX_BOX_BYTES_LENGTH
        op.Box.resize(b"k", 32769)
        # box_splice start > MAX_BOX_BYTES_LENGTH
        op.Box.splice(b"k", 32769, 0, b"")
        # box_splice length > MAX_BOX_BYTES_LENGTH
        op.Box.splice(b"k", 0, 32769, b"")
        # box_splice start + length > MAX_BOX_BYTES_LENGTH
        op.Box.splice(b"k", 16000, 17000, b"")

        # txn group index >= 16 — immediate forms (T as uint8 imm but >= 16)
        log(op.GTxn.fee(20))
        log(op.GTxn.application_args(20, 0))
        log(op.GTxn.application_args(20, runtime_uint64))
        log(op.GITxn.fee(20))
        log(op.GITxn.application_args(20, 0))
        log(op.GITxn.application_args(20, runtime_uint64))
        log(op.gaid(20))
        log(op.gload_uint64(20, 0))

        # txn group index >= 16 — stack-arg forms (T >= 256 forces runtime variant)
        log(op.gaid(256))
        log(op.gload_uint64(256, 0))
        log(op.GTxn.fee(256))
        log(op.GTxn.application_args(256, 0))
        log(op.GTxn.application_args(256, 256))

        # txn array field index > 255
        log(op.Txn.application_args(256))
        log(op.ITxn.application_args(256))
        log(op.GTxn.application_args(0, 256))
        log(op.GITxn.application_args(0, 256))

        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine(inline=False)
def runtime_biguint() -> BigUInt:
    return BigUInt(1)
