from algopy import (
    Application,
    ARC4Contract,
    String,
    UInt64,
    arc4,
)


class RejectVersion(ARC4Contract, avm_version=12):
    """
    Demonstrates `reject_version`: an AVM v12 field on every application call
    transaction that pins the caller to a maximum acceptable callee version.

    The callee's app version is incremented every time its approval or clear
    program is updated. If `reject_version > 0` and the callee's current
    version is **>=** `reject_version`, the AVM rejects the call before any
    bytecode executes. Setting `reject_version = N + 1` means "I accept
    versions 0..N inclusive; refuse if newer".

    Some use cases:
      * Defend against silent upgrades of an integrated dependency.
      * Lock a one-time interaction to a specific audited version.
      * Check (or make sure that) a contract has been properly updated.
    """

    # example: REJECT_VERSION_INNER_CALL
    @arc4.abimethod
    def call_pinned(self, target: Application, max_version: UInt64) -> String:
        """
        Send an inner ApplicationCall that refuses to execute if `target`
        has been upgraded past `max_version`.

        `reject_version = max_version + 1` means "fail unless the callee's
        version is <= max_version". This is the canonical pattern for
        pinning to "the version I audited", forward-compatible with whatever
        version number the caller has actually audited.
        """
        result, _txn = arc4.abi_call[String](
            "hello(string)string",
            "World",
            app_id=target,
            reject_version=max_version + 1,
            fee=0,
        )
        return result

    # example: REJECT_VERSION_INNER_CALL

    # example: REJECT_VERSION_CHECK_BEFORE_CALL
    @arc4.abimethod
    def call_checked(self, target: Application, unsafe_version: UInt64) -> String:
        """
        Check `target.version` explicitly, then call. It reads the same
        counter that `reject_version` is compared against (`target` must be
        an available resource; fails if the app does not exist).

        We use it here to enforce a `min_version`, i.e. make sure a
        contract was actually updated.
        """
        assert target.version > unsafe_version, "target bug has not been patched yet"

        result, _txn = arc4.abi_call[String](
            "hello(string)string",
            "World",
            app_id=target,
            fee=0,
        )
        return result

    # example: REJECT_VERSION_CHECK_BEFORE_CALL
