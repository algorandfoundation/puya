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

- Fixed a miscompilation where `x // x` was unconditionally folded to `1` for both uint64 and biguint, silently eliminating the division-by-zero panic when `x` is zero at runtime.
<!--
### Security

- A bullet item for the Security category.

-->
