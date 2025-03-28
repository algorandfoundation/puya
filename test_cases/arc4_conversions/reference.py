from algopy import Account, Application, Asset, ImmutableArray, Txn, arc4


class ReferenceReturn(arc4.ARC4Contract):
    @arc4.abimethod
    def acc_ret(self) -> Account:
        return Txn.sender

    @arc4.abimethod
    def asset_ret(self) -> Asset:
        return Asset(1234)

    @arc4.abimethod
    def app_ret(self) -> Application:
        return Application(1234)

    @arc4.abimethod
    def store(self, acc: Account, app: Application, asset: Asset) -> None:
        self.acc = acc
        self.asset = asset
        self.app = app

    @arc4.abimethod
    def store_apps(self, apps: ImmutableArray[Application]) -> None:
        self.apps = apps

    @arc4.abimethod
    def store_assets(self, assets: ImmutableArray[Asset]) -> None:
        self.assets = assets

    @arc4.abimethod
    def store_accounts(self, accounts: ImmutableArray[Account]) -> None:
        self.accounts = accounts

    @arc4.abimethod
    def return_apps(self) -> ImmutableArray[Application]:
        return self.apps

    @arc4.abimethod
    def return_assets(self) -> ImmutableArray[Asset]:
        return self.assets

    @arc4.abimethod
    def return_accounts(self) -> ImmutableArray[Account]:
        return self.accounts
