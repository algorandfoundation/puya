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

- A bug where reading the length of a box value directly (e.g. `self.box.value.length`) would silently return 0 when the box did not exist, instead of rejecting the txn. The optimizer combined the read and length intrinsic into a single `box_len` but dropped the box existence assertion.


<!--
### Security

- A bullet item for the Security category.

-->
