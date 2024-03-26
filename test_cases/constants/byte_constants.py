from algopy import Bytes, Contract, UInt64, log, op


class ByteConstantsContract(Contract):
    def approval_program(self) -> UInt64:
        base_64 = Bytes.from_base64("QmFzZSA2NCBlbmNvZGVk")
        base_32 = Bytes.from_base32("IJQXGZJAGMZCAZLOMNXWIZLE")
        base_16 = Bytes.from_hex("4261736520313620656E636F646564")
        utf8 = Bytes(b"UTF-8 Encoded")

        result = base_16 + b"|" + base_64 + b"|" + base_32 + b"|" + utf8
        log(result)
        log(op.itob(result.length))
        return UInt64(1)

    def clear_state_program(self) -> bool:
        return True
