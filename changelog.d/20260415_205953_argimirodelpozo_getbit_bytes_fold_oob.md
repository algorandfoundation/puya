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

- Fixed a miscompilation where `getbit` accessing an out of bounds index in a constant `uint64` would be folded into a constant 0 integer. The AVM should panic in this scenario.

- Fixed a compiler crash when attempting to constant-fold a `getbit` out of bounds index access into a bytes constant.


<!--
### Security

- A bullet item for the Security category.

-->
