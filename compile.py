import os
import subprocess
import sys
from pathlib import Path

from PySide6.scripts.pyside_tool import rcc, uic


# Construct the path to the venv's Python interpreter.
if os.name == "nt":  # Windows
    venv_python = os.path.join(sys.prefix, "Scripts", "python.exe")
else:  # Linux / macOS
    venv_python = os.path.join(sys.prefix, "bin", "python")

force = False
if len(sys.argv) == 2 and sys.argv[1] == "--force":
    del sys.argv[1]
    force = True


def _run_command(output: Path, input: Path, args: list[str] | None = None):

    if input.suffix == ".ui":
        command = 'uic'
    elif input.suffix == ".qrc":
        command = "rcc"
    else:
        raise Exception(f"Unknown file type ({input.suffix})")

    input_mod_time = input.stat().st_mtime_ns
    if output.exists():
        output_mod_time = output.stat().st_mtime_ns
    else:
        output_mod_time = 0

    if not force and input_mod_time <= output_mod_time:
        print(f"Skipping {input}")
        return

    args = args or []
    args = [venv_python, sys.argv[0], command, *args, "-o", str(output), str(input)]

    print(f"Compiling {input} to {output_path}")
    ret = subprocess.run(args, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    if ret.returncode != 0:
        print(f"Failed to compile {input_path} using the folloing args: {args[2:]}")
        sys.exit(ret.returncode)


if len(sys.argv) == 1:
    cwd = os.path.dirname(__file__)
    designer_dir = os.path.join(cwd, "designer")
    ui_dir = os.path.join(cwd, "app", "ui")

    for input_path in Path(designer_dir).glob("*.ui"):
        args = ["--from-imports", "--rc-prefix"]
        output_path = Path(os.path.join(ui_dir, f"ui_{input_path.stem}.py"))
        _run_command(output_path, input_path, args)

    for input_path in Path(designer_dir).glob("*.qrc"):
        output_path = Path(os.path.join(ui_dir, f"rc_{input_path.stem}.py"))
        _run_command(output_path, input_path)

elif sys.argv[1] == "uic":
    del sys.argv[1]
    uic()

elif sys.argv[1] == "rcc":
    del sys.argv[1]
    rcc()
