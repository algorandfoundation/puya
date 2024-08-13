This is PuyaPy's custom typeshed, which is a curated subset of the official MyPy typeshed.
It only includes the required stubs used by PuyaPy as this speeds up MyPy's parsing speed
significantly.

However this means certain python modules such as `enum` or `dataclasses` cannot be used in
PuyaPy stubs unless this typeshed is updated.

The contents of the typeshed are populated by the `scripts/vendor_mypy.py` script, which is used
to vendor new versions of MyPy or to update the stubs included in this typeshed. So to add new
stubs, update that script and rerun.