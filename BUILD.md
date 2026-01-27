# Building RASEN Binary

This guide explains how to build a standalone binary for RASEN that can be distributed without requiring Python installation.

## Prerequisites

- Python 3.12+
- `uv` package manager
- All project dependencies installed (`uv sync`)

## Quick Start

### Option 1: Using Build Script (Recommended)

```bash
# Install PyInstaller
uv pip install pyinstaller

# Run build script
python build.py
```

The script will:
1. Check for PyInstaller (offer to install if missing)
2. Clean previous builds
3. Build the binary
4. Report the output location and size

### Option 2: Manual Build

```bash
# Install PyInstaller
uv pip install pyinstaller

# Build using spec file
pyinstaller --clean rasen.spec

# Binary will be in: dist/rasen (or dist/rasen.exe on Windows)
```

## Output

The binary will be created in the `dist/` directory:

- **macOS/Linux**: `dist/rasen`
- **Windows**: `dist/rasen.exe`

Typical size: 20-40 MB (includes Python runtime and all dependencies)

## Testing the Binary

```bash
# Check version
./dist/rasen --version

# Test help
./dist/rasen --help

# Test init command
./dist/rasen init --task "Test task"

# Test status command
./dist/rasen status
```

## Platform-Specific Builds

### macOS

```bash
# Build on macOS for macOS
python build.py

# For Apple Silicon (M1/M2)
# Binary will automatically target arm64

# For Intel Macs
# Build on Intel Mac or use:
# arch -x86_64 python build.py
```

**Note on macOS**: The binary is not code-signed. Users may need to allow it in Security & Privacy settings on first run.

### Linux

```bash
# Build on Linux for Linux
python build.py

# The binary will target the current architecture (x86_64, arm64, etc.)
```

**Compatibility**: Binary built on older Linux (e.g., Ubuntu 20.04) will work on newer versions. Binary built on newer Linux may not work on older versions.

### Windows

```bash
# Build on Windows for Windows
python build.py

# Output: dist\rasen.exe
```

**Note**: Windows Defender may flag the executable on first run. This is common with PyInstaller binaries.

## Cross-Platform Building

PyInstaller **cannot cross-compile**. You must build on the target platform:

- To create a macOS binary → build on macOS
- To create a Linux binary → build on Linux
- To create a Windows binary → build on Windows

### Using CI/CD for Multi-Platform Builds

Example GitHub Actions workflow (`.github/workflows/build.yml`):

```yaml
name: Build Binaries

on: [push, pull_request]

jobs:
  build:
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
    runs-on: ${{ matrix.os }}

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install pyinstaller
          pip install -e .

      - name: Build binary
        run: python build.py

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: rasen-${{ matrix.os }}
          path: dist/*
```

## Customizing the Build

Edit `rasen.spec` to customize the build:

### Include Additional Files

```python
datas = [
    ('prompts', 'prompts'),           # Already included
    ('docs', 'docs'),                 # Add documentation
    ('examples', 'examples'),         # Add examples
]
```

### Reduce Binary Size

```python
# In rasen.spec, add to excludes:
excludes=[
    'pytest', 'mypy', 'ruff',         # Already excluded
    'PIL',                            # Exclude Pillow if not needed
    'cryptography',                   # Exclude if not needed
],

# Enable UPX compression (already enabled)
upx=True,
```

### Debug Build

For troubleshooting build issues:

```python
# In rasen.spec:
debug=True,           # Enable debug output
console=True,         # Keep console window (already enabled)
```

Then run:
```bash
pyinstaller --clean --debug all rasen.spec
```

## Troubleshooting

### Binary Size Too Large

1. Check what's included: `pyinstaller --clean --log-level=DEBUG rasen.spec`
2. Add unused packages to `excludes` in `rasen.spec`
3. Enable UPX compression (already enabled)
4. Consider using `--onedir` instead of `--onefile` for faster startup

### "Module not found" Errors

Add missing modules to `hiddenimports` in `rasen.spec`:

```python
hiddenimports=[
    'missing_module_name',
]
```

### Binary Crashes on Startup

1. Test with debug build: `pyinstaller --debug all rasen.spec`
2. Run binary from terminal to see error messages
3. Check that data files (prompts/) are included correctly

### macOS "Cannot be opened" Error

```bash
# Remove quarantine attribute
xattr -d com.apple.quarantine dist/rasen

# Or right-click → Open (first time only)
```

### Windows Defender Flags Binary

This is normal for PyInstaller. To avoid:
1. Code sign the binary (requires certificate)
2. Submit to Microsoft for analysis
3. Users can add exception in Windows Defender

## Distribution

### macOS

```bash
# Create DMG (requires create-dmg)
brew install create-dmg

create-dmg \
  --volname "RASEN" \
  --window-pos 200 120 \
  --window-size 800 400 \
  --icon-size 100 \
  --app-drop-link 600 185 \
  rasen-installer.dmg \
  dist/rasen
```

### Linux

```bash
# Create tarball
tar -czf rasen-linux-x86_64.tar.gz -C dist rasen

# Or create .deb package (requires fpm)
fpm -s dir -t deb -n rasen -v 0.1.0 \
  --prefix /usr/local/bin \
  dist/rasen
```

### Windows

```bash
# Create installer (requires Inno Setup)
# Or just distribute the .exe directly
zip rasen-windows.zip dist/rasen.exe
```

## Alternative: Using PyOxidizer

For more advanced builds, consider [PyOxidizer](https://github.com/indygreg/PyOxidizer):

```bash
# Install PyOxidizer
curl -sSf https://install.pyoxidizer.com | sh

# Initialize
pyoxidizer init-config-file

# Build
pyoxidizer build
```

PyOxidizer produces smaller, faster binaries but has a steeper learning curve.

## Alternative: Using Nuitka

For native compilation to C:

```bash
# Install Nuitka
pip install nuitka

# Build
python -m nuitka \
  --onefile \
  --include-data-dir=prompts=prompts \
  src/rasen/cli.py
```

Nuitka produces faster binaries but compilation takes longer.

## Summary

**Recommended approach**:
1. Use `python build.py` for simple, reliable builds
2. Customize `rasen.spec` for advanced options
3. Use CI/CD for multi-platform builds
4. Test binary thoroughly before distribution

**Binary characteristics**:
- Size: 20-40 MB (single file, includes Python runtime)
- Startup: ~1-2 seconds (cold start)
- No Python installation required
- Works on systems without internet access
