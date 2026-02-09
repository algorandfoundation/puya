// This file is auto-generated, do not modify
import * from '@algorandfoundation/algorand-typescript'


export abstract class TicTacToeContract extends Contract {

    @abimethod({ onCreate: 'allow' })
    new_game(
        move: arc4.Tuple<readonly [arc4.Uint<64>, arc4.Uint<64>]>,
    ): void {
        err("stub only")
    }

    @abimethod
    join_game(
        move: arc4.Tuple<readonly [arc4.Uint<64>, arc4.Uint<64>]>,
    ): void {
        err("stub only")
    }

    @abimethod
    whose_turn(

    ): arc4.Uint<8> {
        err("stub only")
    }

    @abimethod
    play(
        move: arc4.Tuple<readonly [arc4.Uint<64>, arc4.Uint<64>]>,
    ): void {
        err("stub only")
    }
}
