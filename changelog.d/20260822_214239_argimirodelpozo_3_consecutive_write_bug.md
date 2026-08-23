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

- A bug in repeated loads elimination. When there were 3 (or more) writes in a row followed by a read in the same basic block all for the same key, the last write in the row would be ignored, and the value of the second write would make it into subsequent reads instead.


<!--
### Security

- A bullet item for the Security category.

-->
