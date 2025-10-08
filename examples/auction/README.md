Port of Beaker auction contract to TEALScript, and then to Algorand Python.
Adapted from original source: https://github.com/algorand-devrel/beaker-auction/tree/7e1fe62b852c0d819954a931f10cf39d841cbc02 with some changes on design and functionality.


# Contract state variables:
- Global State:
    - auction_end, an unsigned 64 bit integer starting at 0 on creation and 
    - self.highest_bid = UInt64(0)
    - self.asa = Asset()
    - self.highest_bidder = Global.zero_address
    - self.claim_time = UInt64(10000)

- Local State:
    - self.claimable_amount = LocalState(UInt64, key="claim", description="The claimable amount")

# Function descriptions
