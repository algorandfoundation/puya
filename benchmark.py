import glob
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any


def generate_options(awst_file: str) -> dict[str, Any]:
    """
    Dynamically generate the options JSON for _PuyaOptionsWithCompilationSet.
    Reads the AWST file and extracts a valid target id from a node of type 'Contract' or 'LogicSignature'.
    Handles AWST JSON files that are either a list or a dict containing a 'nodes' key.
    Returns a dict with 'output_teal' set to True and a 'compilation_set' mapping the target id to the output directory.
    """
    try:
        with open(awst_file, encoding="utf8") as f:
            data = json.load(f)

        if isinstance(data, list):
            nodes = data
        elif isinstance(data, dict):
            nodes = data.get("nodes", [])
        else:
            nodes = []

        target_id: str = ""
        for node in nodes:
            if isinstance(node, dict) and "id" in node and "_type" in node:
                if node["_type"] in ["Contract", "LogicSignature"]:
                    target_id = node["id"]
                    break
        if not target_id:
            target_id = "dummy_target"
    except Exception as e:
        print(f"Failed to read awst file {awst_file}: {e}")
        target_id = "dummy_target"

    return {
        "output_teal": True,
        "output_arc56": True,
        "compilation_set": {
            target_id: str(Path("/home/aorumbayev/MakerX/algokit/puya/benchmark_output/")),
        },
    }


def run_benchmark(awst_file: str, *, mode: str = "python") -> float:
    """
    Runs the benchmark for a given AWST file in the specified mode.
    mode can be:
      - "python" for the Python Package (using poetry),
      - "nuitka_expanded" for the expanded Nuitka binary (./nuitka/__main__.dist/puya-bin),
      - "nuitka_onefile" for the one-file Nuitka binary (/home/aorumbayev/MakerX/algokit/puya/puya).
    """
    print(f"Benchmarking for awst file: {awst_file} using mode '{mode}'")
    options = generate_options(awst_file)
    target_compilation_set = options.get("compilation_set")
    target_key = (
        list(target_compilation_set.keys())[0] if target_compilation_set else "dummy_target"
    )

    if target_key == "dummy_target":
        print(
            f"Skipping benchmarking for {awst_file} because no valid compilation target was found in AWST."
        )
        return 0.0

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as temp_file:
        json.dump(options, temp_file)
        temp_options_path = temp_file.name

    if mode == "python":
        executable: list[str] = ["poetry", "run", "puya"]
    elif mode == "nuitka_expanded":
        executable = ["./nuitka/__main__.dist/puya-bin"]
    elif mode == "nuitka_onefile":
        executable = ["/home/aorumbayev/MakerX/algokit/puya/puya"]
    else:
        print(f"Unknown mode: {mode}. Defaulting to Python package.")
        executable = ["poetry", "run", "puya"]

    cmd: list[str] = executable + ["--awst", awst_file, "--options", temp_options_path]

    print(f"Running command: {' '.join(cmd)}")
    start_time = time.perf_counter()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        elapsed = time.perf_counter() - start_time
        print(f"Completed in {elapsed:.2f} seconds")
        if result.stdout:
            print("Standard Output:")
            print(result.stdout)
    except subprocess.CalledProcessError as e:
        elapsed = time.perf_counter() - start_time
        print(f"Command failed after {elapsed:.2f} seconds")
        print("Error Output:")
        print(e.output)
    finally:
        os.remove(temp_options_path)
    return elapsed


def bench_file(awst_file: str, iterations: int, mode: str) -> float:
    """
    Runs the benchmark for the given AWST file multiple times and returns the average elapsed time.
    """
    times: list[float] = []
    for i in range(iterations):
        print(
            f"Iteration {i+1}/{iterations} for {awst_file} using {'Nuitka Binary Expanded' if mode=='nuitka_expanded' else ('Nuitka Binary OneFile' if mode=='nuitka_onefile' else 'Python package')}..."
        )
        t = run_benchmark(awst_file, mode=mode)
        times.append(t)
    avg_time = sum(times) / iterations if iterations > 0 else 0.0
    print(
        f"Average time for {awst_file} using {'Nuitka Binary Expanded' if mode=='nuitka_expanded' else ('Nuitka Binary OneFile' if mode=='nuitka_onefile' else 'Python package')} over {iterations} iterations: {avg_time:.2f}s"
    )
    return avg_time


def main() -> None:
    """
    Main function to run benchmarks for all module.awst.json files under the examples directory.
    It benchmarks both the Python package and the Nuitka-compiled binary over multiple iterations for each file, then visualizes the results
    using a grouped bar chart and a bar chart with error bars. It also displays the speedup factor.
    """
    awst_files: list[str] = glob.glob("examples/**/module.awst.json", recursive=True)
    if not awst_files:
        print("No awst module.awst.json files found in the examples directory.")
        return

    times_python: list[float] = []
    times_nuitka_expanded: list[float] = []
    times_nuitka_onefile: list[float] = []
    iterations: int = 10  # number of iterations per AWST file

    for awst_file in awst_files:
        print(f"\nBenchmarking {awst_file} using Python package...")
        t_py = bench_file(awst_file, iterations, mode="python")
        times_python.append(t_py)

        print(f"\nBenchmarking {awst_file} using Nuitka Binary Expanded...")
        t_ne = bench_file(awst_file, iterations, mode="nuitka_expanded")
        times_nuitka_expanded.append(t_ne)

        print(f"\nBenchmarking {awst_file} using Nuitka Binary OneFile...")
        t_no = bench_file(awst_file, iterations, mode="nuitka_onefile")
        times_nuitka_onefile.append(t_no)

        print(
            f"Results for {awst_file}: Python package - {t_py:.2f}s, Nuitka Binary Expanded - {t_ne:.2f}s, Nuitka Binary OneFile - {t_no:.2f}s"
        )

    avg_py: float = sum(times_python) / len(times_python)
    avg_ne: float = sum(times_nuitka_expanded) / len(times_nuitka_expanded)
    avg_no: float = sum(times_nuitka_onefile) / len(times_nuitka_onefile)
    print(
        f"\nAverage Time: Python package - {avg_py:.2f}s, Nuitka Binary Expanded - {avg_ne:.2f}s, Nuitka Binary OneFile - {avg_no:.2f}s"
    )

    speedup_expanded: float = avg_py / avg_ne if avg_ne > 0 else float("inf")
    speedup_onefile: float = avg_py / avg_no if avg_no > 0 else float("inf")
    print(
        f"\nOn average, the Nuitka Binary Expanded is {speedup_expanded:.2f} times faster than the Python package."
    )
    print(
        f"On average, the Nuitka Binary OneFile is {speedup_onefile:.2f} times faster than the Python package."
    )

    # Visualization using matplotlib: two subplots (per-file times and average with error bars) for all three modes
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib is not installed. Please install it to view the visualization.")
        return

    import statistics

    std_py: float = statistics.stdev(times_python) if len(times_python) > 1 else 0.0
    std_ne: float = (
        statistics.stdev(times_nuitka_expanded) if len(times_nuitka_expanded) > 1 else 0.0
    )
    std_no: float = (
        statistics.stdev(times_nuitka_onefile) if len(times_nuitka_onefile) > 1 else 0.0
    )

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    # Left subplot: per-AWST-file compilation times for three modes
    width = 0.25
    x = list(range(len(awst_files)))
    ax1.bar([xi - width for xi in x], times_python, width, label="Python Package")
    ax1.bar(x, times_nuitka_expanded, width, label="Nuitka Binary Expanded")
    ax1.bar([xi + width for xi in x], times_nuitka_onefile, width, label="Nuitka Binary OneFile")
    labels = [os.path.basename(os.path.dirname(f)) for f in awst_files]
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=45, ha="right")
    ax1.set_ylabel("Compilation Time (s)")
    ax1.set_title("Compilation Time per AWST File")
    ax1.legend()

    # Right subplot: average compilation times with error bars for three modes
    methods = ["Python Package", "Nuitka Binary Expanded", "Nuitka Binary OneFile"]
    avg_times = [avg_py, avg_ne, avg_no]
    std_devs = [std_py, std_ne, std_no]
    ax2.bar(methods, avg_times, yerr=std_devs, capsize=10, color=["blue", "orange", "purple"])
    ax2.set_ylabel("Average Compilation Time (s)")
    ax2.set_title("Average Compilation Time Comparison")

    # Annotate speedup for each Nuitka mode relative to Python package
    if avg_ne > 0:
        speedup_expanded_text = f"{speedup_expanded:.2f}× faster"
        ax2.text(
            1,
            avg_ne + 0.05 * max(avg_times),
            speedup_expanded_text,
            ha="center",
            fontsize=12,
            color="green",
        )
    if avg_no > 0:
        speedup_onefile_text = f"{speedup_onefile:.2f}× faster"
        ax2.text(
            2,
            avg_no + 0.05 * max(avg_times),
            speedup_onefile_text,
            ha="center",
            fontsize=12,
            color="green",
        )

    plt.tight_layout()
    plt.savefig("benchmark_comparison.png")
    plt.show()


if __name__ == "__main__":
    main()
