// This file is auto-generated, do not modify
import * from '@algorandfoundation/algorand-typescript'


export abstract class TestContract extends Contract {

    @abimethod({ onCreate: 'require' })
    create(
        bool_param: arc4.Bool,
        uint64_param: arc4.Uint<64>,
        bytes_param: arc4.DynamicBytes,
        biguint_param: arc4.Uint<512>,
        string_param: arc4.Str,
        tuple_param: arc4.Tuple<readonly [arc4.Bool, arc4.Uint<64>, arc4.DynamicBytes, arc4.Uint<512>, arc4.Str]>,
    ): arc4.Tuple<readonly [arc4.Bool, arc4.Uint<64>, arc4.DynamicBytes, arc4.Uint<512>, arc4.Str]> {
        err("stub only")
    }

    @abimethod
    tuple_of_arc4(
        args: arc4.Tuple<readonly [arc4.Uint<8>, arc4.Address]>,
    ): arc4.Tuple<readonly [arc4.Uint<8>, arc4.Address]> {
        err("stub only")
    }
}
