# Publishing to PyPI

This document explains how to publish the file-editor package to PyPI.

## Prerequisites

1. **Create PyPI Account**: Register at https://pypi.org/account/register/
2. **Create TestPyPI Account**: Register at https://test.pypi.org/account/register/ (for testing)
3. **Generate API Token**: Go to PyPI account settings and create an API token

## Method 1: Using uv (Recommended)

```bash
# Install publishing tools
uv add --dev twine

# Build the package (already done)
uv build

# Upload to TestPyPI first (recommended for testing)
uv run twine upload --repository testpypi dist/*

# Upload to PyPI (production)
uv run twine upload dist/*
```

## Method 2: Using twine directly

```bash
# Install twine
pip install twine

# Build if not already done
uv build

# Check the distribution
twine check dist/*

# Upload to TestPyPI first
twine upload --repository testpypi dist/*

# Upload to PyPI
twine upload dist/*
```

## Authentication

When prompted, use:
- Username: `__token__`
- Password: Your API token (starts with `pypi-`)

Or create `~/.pypirc`:

```ini
[distutils]
index-servers = pypi testpypi

[pypi]
username = __token__
password = pypi-your-api-token-here

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-your-testpypi-api-token-here
```

## Testing Installation

After uploading to TestPyPI:

```bash
# Install from TestPyPI
pip install --index-url https://test.pypi.org/simple/ file-editor

# Test the package
python -c "from file_editor import AgentFileSystem; print('Success!')"
```

After uploading to PyPI:

```bash
# Install from PyPI
uv add file-editor
# or
pip install file-editor
```

## Version Updates

For future releases:

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md` (create if needed)
3. Commit and tag the release:
   ```bash
   git add .
   git commit -m "Release v0.1.1"
   git tag v0.1.1
   git push && git push --tags
   ```
4. Build and upload new version

## Package Information

- **Package Name**: `file-editor`
- **Current Version**: `0.1.0`
- **Python Support**: `>=3.11`
- **Dependencies**: `filelock>=3.12.0`
- **Optional Dependencies**: `pandas`, `h5py`

## Repository Links

- **Homepage**: https://github.com/rwxproject/file-editor
- **Documentation**: https://github.com/rwxproject/file-editor#readme
- **Bug Tracker**: https://github.com/rwxproject/file-editor/issues

## Distribution Files

The build process creates:
- `dist/file_editor-0.1.0.tar.gz` (source distribution)
- `dist/file_editor-0.1.0-py3-none-any.whl` (wheel distribution)

Both files should be uploaded to PyPI.