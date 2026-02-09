// This file is auto-generated, do not modify
import * from '@algorandfoundation/algorand-typescript'

export class LogMessage extends arc4.Struct<{
    level: arc4.Uint<64>,
    message: arc4.Str,
}> { }

export class LogStruct extends arc4.Struct<{
    level: arc4.Uint<64>,
    message: arc4.Str,
}> { }

export abstract class Logger extends Contract {

    @abimethod
    is_a_b(
        a: arc4.DynamicBytes,
        b: arc4.DynamicBytes,
    ): void {
        err("stub only")
    }

    @abimethod
    echo(
        value: arc4.Str,
    ): arc4.Str {
        err("stub only")
    }

    @abimethod
    no_args(

    ): arc4.Uint<64> {
        err("stub only")
    }

    @abimethod
    log(
        value: arc4.Uint<64>,
    ): void {
        err("stub only")
    }

    @abimethod({ name: 'log' })
    log2(
        value: arc4.Uint<512>,
    ): void {
        err("stub only")
    }

    @abimethod({ name: 'log' })
    log3(
        value: arc4.Str,
    ): void {
        err("stub only")
    }

    @abimethod({ name: 'log' })
    log4(
        value: arc4.Bool,
    ): void {
        err("stub only")
    }

    @abimethod({ name: 'log' })
    log5(
        value: arc4.DynamicBytes,
    ): void {
        err("stub only")
    }

    @abimethod({ name: 'log' })
    log6(
        asset: arc4.Uint<64>,
        account: arc4.Address,
        app: arc4.Uint<64>,
    ): void {
        err("stub only")
    }

    @abimethod({ name: 'log' })
    log7(
        address: arc4.Address,
    ): void {
        err("stub only")
    }

    @abimethod
    echo_native_string(
        value: arc4.Str,
    ): arc4.Str {
        err("stub only")
    }

    @abimethod
    echo_native_bytes(
        value: arc4.DynamicBytes,
    ): arc4.DynamicBytes {
        err("stub only")
    }

    @abimethod
    echo_native_uint64(
        value: arc4.Uint<64>,
    ): arc4.Uint<64> {
        err("stub only")
    }

    @abimethod
    echo_native_biguint(
        value: arc4.Uint<512>,
    ): arc4.Uint<512> {
        err("stub only")
    }

    @abimethod({ resourceEncoding: 'index' })
    echo_resource_by_index(
        asset: Asset,
        app: Application,
        acc: Account,
    ): arc4.Tuple<readonly [arc4.Uint<64>, arc4.Uint<64>, arc4.Address]> {
        err("stub only")
    }

    @abimethod
    echo_resource_by_value(
        asset: arc4.Uint<64>,
        app: arc4.Uint<64>,
        acc: arc4.Address,
    ): arc4.Tuple<readonly [arc4.Uint<64>, arc4.Uint<64>, arc4.Address]> {
        err("stub only")
    }

    @abimethod
    echo_native_tuple(
        s: arc4.Str,
        b: arc4.DynamicBytes,
        u: arc4.Uint<64>,
        bu: arc4.Uint<512>,
    ): arc4.Tuple<readonly [arc4.Str, arc4.DynamicBytes, arc4.Uint<64>, arc4.Uint<512>]> {
        err("stub only")
    }

    @abimethod
    echo_nested_tuple(
        tuple_of_tuples: arc4.Tuple<readonly [arc4.Tuple<readonly [arc4.Str, arc4.Str]>, arc4.Tuple<readonly [arc4.Uint<64>, arc4.Uint<64>, arc4.DynamicBytes]>]>,
    ): arc4.Tuple<readonly [arc4.Tuple<readonly [arc4.Str, arc4.Str]>, arc4.Tuple<readonly [arc4.Uint<64>, arc4.Uint<64>, arc4.DynamicBytes]>]> {
        err("stub only")
    }

    @abimethod
    return_args_after_14th(
        _a1: arc4.Uint<64>,
        _a2: arc4.Uint<64>,
        _a3: arc4.Uint<64>,
        _a4: arc4.Uint<64>,
        _a5: arc4.Uint<64>,
        _a6: arc4.Uint<64>,
        _a7: arc4.Uint<64>,
        _a8: arc4.Uint<64>,
        _a9: arc4.Uint<64>,
        _a10: arc4.Uint<64>,
        _a11: arc4.Uint<64>,
        _a12: arc4.Uint<64>,
        _a13: arc4.Uint<64>,
        _a14: arc4.Uint<64>,
        a15: arc4.Uint<8>,
        a16: arc4.Uint<8>,
        a17: arc4.Uint<8>,
        a18: arc4.Uint<8>,
        a19: arc4.Tuple<readonly [arc4.Uint<8>, arc4.Uint<8>, arc4.Uint<8>, arc4.Uint<8>]>,
        a20: arc4.Uint<8>,
    ): arc4.DynamicBytes {
        err("stub only")
    }

    @abimethod
    logs_are_equal(
        log_1: LogMessage,
        log_2: LogMessage,
    ): arc4.Bool {
        err("stub only")
    }

    @abimethod
    echo_log_struct(
        log: LogStruct,
    ): LogStruct {
        err("stub only")
    }
}
