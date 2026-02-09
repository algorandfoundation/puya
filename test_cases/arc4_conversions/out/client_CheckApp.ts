// This file is auto-generated, do not modify
import * from '@algorandfoundation/algorand-typescript'


export abstract class CheckApp extends Contract {

    @abimethod({ allowActions: ['DeleteApplication'] })
    delete_application(

    ): void {
        err("stub only")
    }

    @abimethod
    check_uint64(
        value: arc4.Uint<64>,
        expected: arc4.DynamicBytes,
    ): void {
        err("stub only")
    }

    @abimethod
    check_dynamic_bytes(
        value: arc4.DynamicBytes,
        expected: arc4.DynamicBytes,
    ): void {
        err("stub only")
    }

    @abimethod
    check_string(
        value: arc4.Str,
        expected: arc4.DynamicBytes,
    ): void {
        err("stub only")
    }

    @abimethod
    check_biguint(
        value: arc4.Uint<512>,
        expected: arc4.DynamicBytes,
    ): void {
        err("stub only")
    }

    @abimethod
    check_bool(
        value: arc4.Bool,
        expected: arc4.DynamicBytes,
    ): void {
        err("stub only")
    }

    @abimethod
    check_dyn_array_uin64(
        value: arc4.DynamicArray<arc4.Uint<64>>,
        expected: arc4.DynamicBytes,
    ): void {
        err("stub only")
    }

    @abimethod
    check_static_array_uin64_3(
        value: FixedArray<arc4.Uint<64>, 3>,
        expected: arc4.DynamicBytes,
    ): void {
        err("stub only")
    }

    @abimethod
    check_dyn_array_struct(
        value: arc4.DynamicArray<arc4.Tuple<readonly [arc4.Uint<64>, arc4.Address]>>,
        expected: arc4.DynamicBytes,
    ): void {
        err("stub only")
    }

    @abimethod
    check_static_array_struct(
        value: FixedArray<arc4.Tuple<readonly [arc4.Uint<64>, arc4.Address]>, 3>,
        expected: arc4.DynamicBytes,
    ): void {
        err("stub only")
    }

    @abimethod
    check_dyn_array_dyn_struct(
        value: arc4.DynamicArray<arc4.Tuple<readonly [arc4.Uint<64>, arc4.Address, arc4.DynamicBytes]>>,
        expected: arc4.DynamicBytes,
    ): void {
        err("stub only")
    }

    @abimethod
    check_static_array_dyn_struct(
        value: FixedArray<arc4.Tuple<readonly [arc4.Uint<64>, arc4.Address, arc4.DynamicBytes]>, 3>,
        expected: arc4.DynamicBytes,
    ): void {
        err("stub only")
    }

    @abimethod
    check_static_bytes(
        bytes32: FixedArray<arc4.Byte, 32>,
    ): void {
        err("stub only")
    }
}
