from puyapy import ARC4Contract, Bytes, arc4, log


class Logger(ARC4Contract):
    @arc4.abimethod
    def echo(self, value: arc4.String) -> arc4.String:
        return "echo: " + value

    @arc4.abimethod
    def log_uint64(self, value: arc4.UInt64) -> None:
        log(value)

    @arc4.abimethod
    def log_uint512(self, value: arc4.UInt512) -> None:
        log(value)

    @arc4.abimethod
    def log_string(self, value: arc4.String) -> None:
        log(value.decode())  # decode to remove header

    @arc4.abimethod
    def log_bool(self, value: arc4.Bool) -> None:
        log(Bytes(b"True") if value.decode() else Bytes(b"False"))

    @arc4.abimethod
    def log_bytes(self, value: arc4.DynamicBytes) -> None:
        log(value.bytes[2:])  # decode to remove header


class LoggerClient(arc4.ARC4Client):
    @arc4.abimethod
    def echo(self, value: arc4.String) -> arc4.String:
        raise NotImplementedError
