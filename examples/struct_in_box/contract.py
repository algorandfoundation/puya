from algopy import ARC4Contract, Asset, arc4, op, subroutine


class UserStruct(arc4.Struct):
    name: arc4.String
    id: arc4.UInt64
    asset: arc4.UInt64


class ExampleContract(ARC4Contract):
    @subroutine
    def read_from_box(self, user_id: arc4.UInt64) -> UserStruct:
        box_data, exists = op.Box.get(user_id.bytes)
        assert exists, "User with that id does not exist"
        return UserStruct.from_bytes(box_data)

    @subroutine
    def write_to_box(self, user: UserStruct) -> None:
        box_key = user.id.bytes
        # Delete existing data, so we don't have to worry about resizing the box
        op.Box.delete(box_key)

        op.Box.put(box_key, user.bytes)

    @subroutine
    def box_exists(self, user_id: arc4.UInt64) -> bool:
        _data, exists = op.Box.get(user_id.bytes)
        return exists

    @arc4.abimethod()
    def add_user(self, user: UserStruct) -> None:
        assert not self.box_exists(user.id), "User with id must not exist"
        self.write_to_box(user)

    @arc4.abimethod()
    def attach_asset_to_user(self, user_id: arc4.UInt64, asset: Asset) -> None:
        user = self.read_from_box(user_id)
        user.asset = arc4.UInt64(asset.id)
        self.write_to_box(user)

    @arc4.abimethod()
    def get_user(self, user_id: arc4.UInt64) -> UserStruct:
        return self.read_from_box(user_id)
