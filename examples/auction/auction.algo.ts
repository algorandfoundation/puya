import { Contract } from '../../src/lib/index';

// eslint-disable-next-line no-unused-vars
class Auction extends Contract {
  previousBidder = GlobalStateKey<Address>();

  auctionEnd = GlobalStateKey<uint64>();

  previousBid = GlobalStateKey<uint64>();

  asaAmt = GlobalStateKey<uint64>();

  asa = GlobalStateKey<Asset>();

  claimableAmount = LocalStateKey<uint64>();

  createApplication(): void {
    this.auctionEnd.value = 0;
    this.previousBid.value = 0;
    this.asaAmt.value = 0;
    this.asa.value = Asset.zeroIndex;

    // Use zero address rather than an empty string for Account type safety
    this.previousBidder.value = globals.zeroAddress;
  }

  optIntoAsset(asset: Asset): void {
    /// Only allow app creator to opt the app account into a ASA
    verifyTxn(this.txn, { sender: globals.creatorAddress });

    /// Verify a ASA hasn't already been opted into
    assert(this.asa.value === Asset.zeroIndex);

    /// Save ASA ID in global state
    this.asa.value = asset;

    /// Submit opt-in transaction: 0 asset transfer to self
    sendAssetTransfer({
      assetReceiver: this.app.address,
      xferAsset: asset,
      assetAmount: 0,
    });
  }

  startAuction(startingPrice: uint64, length: uint64, axfer: AssetTransferTxn): void {
    verifyTxn(this.txn, { sender: globals.creatorAddress });

    /// Ensure the auction hasn't already been started
    assert(this.auctionEnd.value === 0);

    /// Verify axfer
    verifyTxn(axfer, { assetReceiver: this.app.address });

    /// Set global state
    this.asaAmt.value = axfer.assetAmount;
    this.auctionEnd.value = globals.latestTimestamp + length;
    this.previousBid.value = startingPrice;
  }

  private pay(receiver: Account, amount: uint64): void {
    sendPayment({
      receiver: receiver,
      amount: amount,
    });
  }

  optInToApplication(): void {}

  // eslint-disable-next-line no-unused-vars
  bid(payment: PayTxn): void {
    /// Ensure auction hasn't ended
    assert(globals.latestTimestamp < this.auctionEnd.value);

    /// Verify payment transaction
    verifyTxn(payment, {
      sender: this.txn.sender,
      amount: { greaterThan: this.previousBid.value },
    });

    /// Set global state
    this.previousBid.value = payment.amount;
    this.previousBidder.value = payment.sender;

    /// Update claimable amount
    this.claimableAmount(this.txn.sender).value = payment.amount;
  }

  claimBids(): void {
    const originalAmount = this.claimableAmount(this.txn.sender).value;
    let amount = originalAmount;

    /// subtract previous bid if sender is previous bidder
    if (this.txn.sender === this.previousBidder.value) amount = amount - this.previousBid.value;

    this.pay(this.txn.sender, amount);
    this.claimableAmount(this.txn.sender).value = originalAmount - amount;
  }

  claim_asset(asset: Asset): void {
    assert(globals.latestTimestamp > this.auctionEnd.value);

    /// Send ASA to previous bidder
    sendAssetTransfer({
      assetReceiver: this.previousBidder.value,
      xferAsset: asset,
      assetAmount: this.asaAmt.value,
      assetCloseTo: this.previousBidder.value,
    });
  }

  deleteApplication(): void {
    sendPayment({
      receiver: globals.creatorAddress,
      closeRemainderTo: globals.creatorAddress,
      amount: 0,
    });
  }
}
