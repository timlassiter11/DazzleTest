import os
import sys
import sysconfig

from cx_Freeze import Executable, setup

from app import APP_AUTHOR, APP_DESCRIPTION, APP_NAME

app_name = APP_NAME
description = APP_DESCRIPTION
author = APP_AUTHOR
icon = "./assets/icons/icon.ico"


upgrade_code = "3799EFA4-C852-3F61-8004-16BDAB266CF5"
# Start Menu Folder
start_folder = ""


base = "Win32GUI" if sys.platform == "win32" else None
install_dir = (
    "ProgramFiles64Folder"
    if sysconfig.get_platform() == "win-amd64"
    else "ProgramFilesFolder"
)


build_exe_options = {
    "zip_include_packages": ["encoder", "PySide6"],
    "include_msvcr": True,
    "include_files": [
        ("test_images", "test_images")
    ],
    "excludes": [
        "tkinter",
        "wheel",
        "setuptools",
        "setuptools_scm",
        "unittest",
    ],
}

# Used to create the start menu folder
# https://learn.microsoft.com/en-us/windows/win32/msi/directory-table
directory_table = [
    ("ProgramMenuFolder", "TARGETDIR", "."),
    ("ProgramMenuSubFolder", "ProgramMenuFolder", start_folder or "."),
]

msi_data = {"Directory": directory_table}

bdist_msi_options = {
    "data": msi_data,
    "upgrade_code": f"{{{upgrade_code}}}" if upgrade_code else None,
    "summary_data": {"author": author},
    "initial_target_dir": f"[{install_dir}]{app_name}",
    "install_icon": icon,
}

executable = Executable(
    script="main.py",
    base=base,
    target_name=app_name,
    icon=icon,
    shortcut_name=app_name,
    shortcut_dir="ProgramMenuSubFolder",
)

setup(
    name=app_name,
    description=description,
    options={
        "build_exe": build_exe_options,
        "bdist_msi": bdist_msi_options,
    },
    executables=[executable],
    use_scm_version={"write_to": "app/_version.py"},
    setup_requires=["setuptools_scm"],
)
