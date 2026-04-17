<!--
A new scriv changelog fragment.

Uncomment the section that is right (remove the HTML comment wrapper).
For top level release notes, leave all the headers commented out.
-->

<!--
### Removed

- A bullet item for the Removed category.

-->
<!--
### Added

- A bullet item for the Added category.

-->
<!--
### Changed

- A bullet item for the Changed category.

-->
<!--
### Deprecated

- A bullet item for the Deprecated category.

-->
### Fixed

- Fixed an issue where `shl`/`shr` with a shift amount >= 64 on `uint64` constants was folded to 0 
  instead of preserving the AVM runtime panic.

<!--
### Security

- A bullet item for the Security category.

-->
