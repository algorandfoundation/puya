### Added

- `Box` can now refer to a box belonging to _another_ application, via the AVM 13 `app_box_*`
  opcodes. Construct one with `Box.remote()`:

  ```python
  box = Box.remote(UInt64, app=other_app, key=b"counter")
  assert box.value == 42
  ```

  A box's location is part of its type - `Box` gained a second, defaulted type parameter, so
  `Box[UInt64]` means `Box[UInt64, Local]` as before, and `Box.remote()` returns
  `Box[UInt64, Remote]`. The full `Box` API is available for both locations, other than the
  deprecated `.ref` member, which is local-only. `.app` is new, and reports the current
  application on local boxes.

  A remote box is not part of the declaring contract's state, so it cannot be declared as a
  contract member and does not appear in the generated ARC-32/ARC-56 state. Values whose
  encoded size is statically known to exceed 4096 bytes are rejected at compile time - use
  `.extract()` and `.replace()` to access such a box in chunks.
