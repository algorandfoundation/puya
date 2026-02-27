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

- Round-trip encoding of ARC-4 integers via `BigUInt` is now optimized away.

<!--
### Changed

- A bullet item for the Changed category.

-->
<!--
### Deprecated

- A bullet item for the Deprecated category.

-->

### Fixed

- Fixed optimizer incorrectly eliminating round-trip encoding of large ARC-4 integers (N>64) via `UInt64`.

<!--
### Security

- A bullet item for the Security category.

-->
