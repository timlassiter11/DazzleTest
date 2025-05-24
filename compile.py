"""
Build script for compiling Qt UI (.ui) and Resource (.qrc) files for the DazzleTest application.

This script automates the conversion of Qt Designer's UI files and Qt Resource Collection
files into Python modules that can be imported and used within the PySide6 application.

It provides two main modes of operation:
1. Batch mode (no arguments or --force): Compiles all .ui and .qrc files found
   in the `designer/` directory and places the output Python files in `app/ui/`.
   It checks timestamps to avoid recompiling unchanged files unless `--force` is used.
2. Passthrough mode: If called with `uic` or `rcc` as the first argument, it behaves
   like the standard PySide6 `uic` or `rcc` command-line tools, respectively.
   This allows for direct invocation of these tools using this script as a wrapper.

The script ensures it uses the Python interpreter from the current virtual environment
to run the PySide6 tools, maintaining consistency.
"""
import os
import subprocess
import sys
from pathlib import Path # For object-oriented path manipulation

# Import the uic (UI Compiler) and rcc (Resource Compiler) functions
# from PySide6.scripts.pyside_tool. These are the actual tools provided by PySide6.
from PySide6.scripts.pyside_tool import rcc, uic


# Determine the path to the Python interpreter within the current virtual environment.
# This is crucial for ensuring that the PySide6 tools (uic, rcc) are run with the
# correct Python interpreter and environment that has PySide6 installed.
if os.name == "nt":  # Check if the operating system is Windows
    # On Windows, the venv Python executable is typically in VENV_ROOT\Scripts\python.exe
    venv_python = os.path.join(sys.prefix, "Scripts", "python.exe")
else:  # For Linux, macOS, and other POSIX-like systems
    # On POSIX systems, it's typically in VENV_ROOT/bin/python
    venv_python = os.path.join(sys.prefix, "bin", "python")

# --- Command-line Argument Parsing ---
# Check for a "--force" argument to compel recompilation even if files are up-to-date.
force = False
if len(sys.argv) > 1 and sys.argv[1] == "--force":
    del sys.argv[1]  # Remove the --force argument so it's not passed to uic/rcc
    force = True     # Set the force flag


def _run_command(output_file: Path, input_file: Path, extra_args: list[str] | None = None):
    """
    Helper function to execute the uic or rcc command for a single file.

    It checks file modification times to skip compilation if the output is newer
    than the input, unless the global `force` flag is True.

    Args:
        output_file: The Path object for the target Python output file.
        input_file: The Path object for the source .ui or .qrc file.
        extra_args: A list of additional command-line arguments for uic/rcc.
    """

    # Determine which command (uic or rcc) to use based on the input file's suffix.
    if input_file.suffix == ".ui":
        command_name = 'uic'
    elif input_file.suffix == ".qrc":
        command_name = "rcc"
    else:
        # Should not happen if called correctly from the main script logic.
        raise ValueError(f"Unsupported file type for compilation: {input_file.suffix}")

    # Get modification time of the input file.
    input_mod_time = input_file.stat().st_mtime_ns
    # Get modification time of the output file, or 0 if it doesn't exist.
    if output_file.exists():
        output_mod_time = output_file.stat().st_mtime_ns
    else:
        output_mod_time = 0 # Output doesn't exist, so it's older

    # Skip compilation if the input file is not newer than the output file,
    # and the --force flag is not set.
    if not force and input_mod_time <= output_mod_time:
        print(f"Skipping {input_file} (output is up-to-date).")
        return

    # Prepare arguments for the subprocess call.
    # The command will be: `venv_python compile.py <uic|rcc> [extra_args] -o output_file input_file`
    # This script (compile.py) is called again, but then it routes to the direct uic()/rcc() calls.
    final_args = extra_args or []
    # Construct the full command: [python_interpreter, this_script, tool_name, ...tool_args..., -o, output_path, input_path]
    command_line = [venv_python, sys.argv[0], command_name, *final_args, "-o", str(output_file), str(input_file)]

    print(f"Compiling {input_file} to {output_file} using '{command_name}'...")
    # Run the compilation command as a subprocess.
    process_result = subprocess.run(command_line, capture_output=True, text=True, check=False)

    # Check if the command was successful.
    if process_result.returncode != 0:
        # If compilation failed, print error messages and exit.
        print(f"Failed to compile {input_file}.")
        print(f"Command: {' '.join(command_line)}") # For debugging
        print(f"Stdout:\n{process_result.stdout}")
        print(f"Stderr:\n{process_result.stderr}")
        sys.exit(process_result.returncode)
    else:
        if process_result.stdout: # Print any standard output from the tool
             print(process_result.stdout)
        if process_result.stderr: # Print any standard error (warnings, etc.)
             print(f"Warnings/Messages from {command_name} for {input_file}:\n{process_result.stderr}")


# --- Main Script Logic ---

# If the script is run with no arguments (or only --force, which is handled already),
# it enters batch compilation mode.
if len(sys.argv) == 1:
    # Determine current working directory and paths to designer (input) and app/ui (output) directories.
    current_dir = Path(__file__).resolve().parent # Get the directory where compile.py resides
    designer_input_dir = current_dir / "designer"
    ui_output_dir = current_dir / "app" / "ui"

    # Ensure the output directory exists.
    ui_output_dir.mkdir(parents=True, exist_ok=True)

    # Compile all .ui files from the designer directory.
    print(f"Searching for .ui files in {designer_input_dir}...")
    for ui_input_file in designer_input_dir.glob("*.ui"):
        # Define specific arguments for uic.
        # `--from-imports`: Generate Python import statements relative to the project structure.
        # `--rc-prefix`: (If you were using .qrc files directly in .ui, this would be relevant)
        #                For .ui files, this might not be strictly necessary unless resources are named.
        #                It's often used with `pyside6-uic --rc-prefix /` for example.
        #                Here, it seems like a general argument that might be passed.
        uic_args = ["--from-imports"] # Removed --rc-prefix as it's not typically used like this for uic alone
                                     # and might cause issues if no .qrc is directly referenced in the .ui.
                                     # If specific .qrc files are linked in .ui files, this might need adjustment
                                     # or the .qrc files should be compiled first.
        # Define the output Python file path, prefixing with "ui_".
        py_output_file = ui_output_dir / f"ui_{ui_input_file.stem}.py"
        _run_command(py_output_file, ui_input_file, uic_args)

    # Compile all .qrc files from the designer directory.
    print(f"\nSearching for .qrc files in {designer_input_dir}...")
    for qrc_input_file in designer_input_dir.glob("*.qrc"):
        # Define the output Python file path, prefixing with "rc_".
        py_output_file = ui_output_dir / f"rc_{qrc_input_file.stem}.py"
        _run_command(py_output_file, qrc_input_file) # No extra args typically needed for rcc

# If the script is called with "uic" as the first argument (after stripping --force),
# it acts as a passthrough to the PySide6 uic tool.
# Example: `python compile.py uic mydialog.ui -o mydialog.py`
elif sys.argv[1] == "uic":
    del sys.argv[1]  # Remove "uic" from args, the rest are for the actual uic tool
    uic()            # Call the imported uic function from PySide6

# If the script is called with "rcc" as the first argument,
# it acts as a passthrough to the PySide6 rcc tool.
# Example: `python compile.py rcc resources.qrc -o rc_resources.py`
elif sys.argv[1] == "rcc":
    del sys.argv[1]  # Remove "rcc" from args
    rcc()            # Call the imported rcc function from PySide6
else:
    # Handle cases where arguments are provided but not recognized as uic/rcc commands
    # or the batch mode trigger.
    if len(sys.argv) > 1: # if it wasn't just --force that got stripped
        print(f"Unknown command or arguments: {' '.join(sys.argv[1:])}", file=sys.stderr)
        print("Usage: python compile.py [--force | uic [uic_args] | rcc [rcc_args]]", file=sys.stderr)
        sys.exit(1)
