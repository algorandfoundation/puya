<!--
A new scriv changelog fragment.

Uncomment the section that is right (remove the HTML comment wrapper).
For top level release notes, leave all the headers commented out.
-->

<!--
### Removed

- A bullet item for the Removed category.

-->

### Added

- Support for new AVM 13 opcodes and fields:
    - New hashing primitives: SHA512 and poseidon2. 
    - `AppBox` family ops, a series of opcodes used to read and write boxes from other applications.
    - `app_params_set` and two new boolean settable `AppParams` fields: `AppForeignBoxReads` (indicates that this app's boxes may be read by any app) and `AppFamilyBoxAccess` (indicates that this app's boxes may be read and written by any app -existing or future- with the same creator).
    - New application parameter `AppSizeSponsor`: an address which, if non-zero, is responsible for the app's extra pages and global storage MBR.


<!--
### Changed

- A bullet item for the Changed category.

-->
<!--
### Deprecated

- A bullet item for the Deprecated category.

-->
<!--
### Fixed

- A bullet item for the Fixed category.

-->
<!--
### Security

- A bullet item for the Security category.

-->
