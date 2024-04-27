def prioritize_local_algopy_over_stubs() -> None:
    import sys
    from pathlib import Path

    # Ensure the local src directory is prioritized in the Python path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
