"""
Setup script for building the DazzleTest application using cx_Freeze.

This script configures the build process for creating a standalone executable
and an MSI installer for Windows. It uses setuptools_scm for version management.

Key functionalities:
- Defines application metadata (name, description, author).
- Specifies options for building the executable (`build_exe_options`), including
  package inclusions/exclusions and inclusion of necessary files (e.g., MSVCR, test images).
- Configures MSI installer properties (`bdist_msi_options`), such as upgrade code,
  Start Menu shortcut creation, and installation directory.
- Uses `setuptools_scm` to automatically manage the application version based on
  Git tags, writing it to `app/_version.py`.
"""
import os
import sys
import sysconfig # For determining system-specific paths and configurations

# Import necessary components from cx_Freeze for building executables
from cx_Freeze import Executable, setup

# Import application-specific metadata from the app package
from app import APP_AUTHOR, APP_DESCRIPTION, APP_NAME

# --- Application Metadata ---
app_name = APP_NAME  #: The name of the application.
description = APP_DESCRIPTION #: A short description of the application.
author = APP_AUTHOR #: The author of the application.
icon = "./assets/icons/icon.ico" #: Path to the application icon file (used for executable and installer).


# --- MSI Installer Configuration ---
# Upgrade code for the MSI installer. This GUID should be unique for the application
# and remain constant across versions to allow seamless upgrades.
upgrade_code = "3799EFA4-C852-3F61-8004-16BDAB266CF5"
# Name of the Start Menu folder where the application shortcut will be placed.
# If empty, the shortcut is placed directly in the Program Menu.
start_folder = "" # e.g., "MyCompanyName" or "DazzleTest"


# --- Platform-Specific Configuration ---
# Determine the base for the executable. For Windows GUI applications, this is "Win32GUI".
# For console applications or other platforms, it's None.
base = "Win32GUI" if sys.platform == "win32" else None

# Determine the default installation directory based on the system architecture.
# Uses "ProgramFiles64Folder" for 64-bit Windows, "ProgramFilesFolder" otherwise.
# These are MSI properties representing standard Program Files directories.
install_dir = (
    "ProgramFiles64Folder"
    if sysconfig.get_platform() == "win-amd64"
    else "ProgramFilesFolder"
)


# --- cx_Freeze Build Options ---
# Options for the `build_exe` command (building the executable).
build_exe_options = {
    # Packages to include in the zip file (part of the build).
    # "encoder" might be a specific local package. "PySide6" is the Qt bindings.
    "zip_include_packages": ["encoder", "PySide6"],
    # Ensure Microsoft Visual C++ Redistributable (MSVCR) files are included if needed.
    "include_msvcr": True,
    # List of files and directories to include in the build.
    # Each tuple is (source_path, destination_path_in_build_dir).
    # Here, it copies the "test_images" directory into the build.
    "include_files": [
        ("test_images", "test_images") # Copies the local 'test_images' folder to 'test_images' in the build
    ],
    # List of packages to exclude from the build. This can help reduce build size.
    "excludes": [
        "tkinter",          # GUI library, not needed if using PySide6
        "wheel",            # Packaging library, not needed at runtime
        "setuptools",       # Build system, not needed at runtime
        "setuptools_scm",   # Used for versioning at build time, not runtime
        "unittest",         # Standard library for testing, not needed at runtime
    ],
}

# Configuration for creating the Start Menu shortcut via the MSI Directory table.
# See: https://learn.microsoft.com/en-us/windows/win32/msi/directory-table
directory_table = [
    # Defines "ProgramMenuFolder" as a standard MSI property pointing to the Start Menu.
    ("ProgramMenuFolder", "TARGETDIR", "."), # TARGETDIR is the root installation directory
    # Defines "ProgramMenuSubFolder" within "ProgramMenuFolder".
    # 'start_folder' (defined above) determines the subfolder name. If empty, uses ProgramMenuFolder itself.
    ("ProgramMenuSubFolder", "ProgramMenuFolder", start_folder or "."),
]

# Data for the MSI installer, including the directory table.
msi_data = {"Directory": directory_table}

# Options for the `bdist_msi` command (creating the MSI installer).
bdist_msi_options = {
    "data": msi_data, # Includes the Directory table for Start Menu shortcuts.
    # Sets the upgrade code for the MSI, allowing for in-place upgrades.
    "upgrade_code": f"{{{upgrade_code}}}" if upgrade_code else None,
    # Summary information for the MSI installer properties.
    "summary_data": {"author": author},
    # Default installation path for the application.
    # `[install_dir]` is an MSI property (e.g., ProgramFiles64Folder) resolved at install time.
    "initial_target_dir": f"[{install_dir}]{os.sep}{app_name}", # e.g., "C:\Program Files\DazzleTest"
    # Icon to be used for the installer itself and for Add/Remove Programs.
    "install_icon": icon,
}

# --- Executable Definition ---
# Defines the main executable to be built by cx_Freeze.
executable = Executable(
    script="main.py",               # The main script to run the application.
    base=base,                      # "Win32GUI" for Windows GUI apps, None otherwise.
    target_name=f"{app_name}.exe",  # Name of the output executable file.
    icon=icon,                      # Icon for the executable.
    shortcut_name=app_name,         # Name of the Start Menu shortcut.
    shortcut_dir="ProgramMenuSubFolder", # Directory in Start Menu for the shortcut (defined in directory_table).
)

# --- Main Setup Configuration ---
# Calls the cx_Freeze setup function to configure the build.
setup(
    name=app_name,        #: Name of the application (used in metadata).
    description=description, #: Application description (used in metadata).
    options={
        "build_exe": build_exe_options, # Passes the build_exe options.
        "bdist_msi": bdist_msi_options, # Passes the bdist_msi options.
    },
    executables=[executable], #: List of executables to build (just one in this case).
    # Configures setuptools_scm to manage the application version.
    # It writes the version to `app/_version.py`, which can be imported by the app.
    use_scm_version={"write_to": "app/_version.py"},
    # Specifies `setuptools_scm` as a build-time dependency.
    setup_requires=["setuptools_scm"],
)
