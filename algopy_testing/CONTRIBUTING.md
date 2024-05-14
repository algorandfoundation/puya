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
-   **Reset environments:** `hatch env prune` (Useful for resyncing compiler/stub changes with the environment)

# Development Scripts

-   **Regenerate typed clients for example contracts:** `hatch run refresh_test_artifacts`
-   **Coverage check of existing progress on implementing AlgoPy Stubs:** `hatch run check_stubs_cov`
