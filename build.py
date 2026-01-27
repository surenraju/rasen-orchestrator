#!/usr/bin/env python3
"""Build script for creating RASEN standalone binary."""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path


def check_pyinstaller() -> bool:
    """Check if PyInstaller is installed."""
    try:
        subprocess.run(["pyinstaller", "--version"], check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def install_pyinstaller() -> None:
    """Install PyInstaller."""
    print("Installing PyInstaller...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
    print("✅ PyInstaller installed")


def build_binary() -> None:
    """Build standalone binary using PyInstaller."""
    project_root = Path(__file__).parent
    spec_file = project_root / "rasen.spec"

    if not spec_file.exists():
        print("Error: rasen.spec not found. Run this script from project root.")
        sys.exit(1)

    print("Building RASEN binary...")
    print(f"Platform: {platform.system()} {platform.machine()}")
    print(f"Python: {sys.version}")

    # Clean previous builds
    dist_dir = project_root / "dist"
    build_dir = project_root / "build"

    if dist_dir.exists():
        print("Cleaning dist/ directory...")
        shutil.rmtree(dist_dir)

    if build_dir.exists():
        print("Cleaning build/ directory...")
        shutil.rmtree(build_dir)

    # Run PyInstaller
    cmd = ["pyinstaller", "--clean", str(spec_file)]
    subprocess.run(cmd, check=True)

    # Check output
    system = platform.system()
    if system == "Windows":
        binary_name = "rasen.exe"
    else:
        binary_name = "rasen"

    binary_path = dist_dir / binary_name

    if binary_path.exists():
        size_mb = binary_path.stat().st_size / (1024 * 1024)
        print(f"\n✅ Binary built successfully!")
        print(f"   Location: {binary_path}")
        print(f"   Size: {size_mb:.1f} MB")
        print(f"\nTest it with: {binary_path} --version")
    else:
        print("\n❌ Binary not found. Check build logs above.")
        sys.exit(1)


def main() -> None:
    """Main build script."""
    if not check_pyinstaller():
        print("PyInstaller not found.")
        response = input("Install PyInstaller? (y/n): ")
        if response.lower() == "y":
            install_pyinstaller()
        else:
            print("PyInstaller required to build binary. Exiting.")
            sys.exit(1)

    build_binary()


if __name__ == "__main__":
    main()
