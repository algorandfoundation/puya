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

- Fixed an issue where `setbit` with an out-of-bounds index (>= 64) on a uint64 constant was 
  folded instead of preserving the AVM runtime panic.

<!--
### Security

- A bullet item for the Security category.

-->
