# Development dependencies

# Development Dependencies

Our development environment relies on the following tools:

-   **Python 3.12**
-   **[Hatch](https://hatch.pypa.io/1.9/install/)**: A modern, extensible Python project manager.

## Common Commands

Here are some common commands you will use with Hatch:

-   **Pre-commit checks:** `hatch run pre_commit`
-   **Run tests:** `hatch run tests`
-   **Build project:** `hatch build`
-   **Open shell:** `hatch shell`
-   **Reset environments:** `hatch env prune`

# Development Scripts

-   **Regenerate typed clients for example contracts:** `hatch run refresh_test_artifacts`
-   **Coverage check of existing progress on implementing AlgoPy Stubs:** `hatch run check_stubs_cov`

# Examples folder

Examples folder uses a dedicated 'venv.examples' virtual environment managed by Hatch that simulates a user environment with both algorand-python and algorand-python-testing installed explicitly. This is useful for testing new features or bug fixes in the testing library.
