<!--
A new scriv changelog fragment.

Uncomment the section that is right (remove the HTML comment wrapper).
For top level release notes, leave all the headers commented out.
-->

### Added

- Off-curve autosalt: a logicsig whose program hash (concatenated to the domain separator `Program`) decodes to an Edwards25519 point gets a trailing `intcblock` salt (regardless of AVM version) at assemble time, so its address cannot double as a valid public key. Contracts are never salted by default.
- `autosalt` option on the `logicsig` decorator and `Contract` classes to override the default:
  `True` forces salting, `False` disables it, and contradicting overrides emit a warning. The resolved setting is recorded as `#pragma autosalt` in the TEAL output.
