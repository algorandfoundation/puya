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

- Fixed an optimizer bug where a value read from a box could be replaced with a read of the box at the point it is used, after the box had been modified (e.g. by a write, a subroutine call or an inner transaction). This would cause the read of a supposed copy to observe those modifications, basically making it behave like a reference instead.

<!--
### Security

- A bullet item for the Security category.

-->
