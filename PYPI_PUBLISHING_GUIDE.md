# Complete Guide to Publishing Python Packages to PyPI

This comprehensive guide covers everything you need to know about publishing Python packages to PyPI, from initial setup to ongoing maintenance.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Package Preparation](#package-preparation)
3. [PyPI Account Setup](#pypi-account-setup)
4. [Publishing Methods](#publishing-methods)
5. [Testing and Verification](#testing-and-verification)
6. [Troubleshooting](#troubleshooting)
7. [Best Practices](#best-practices)
8. [Automation and CI/CD](#automation-and-cicd)

## Prerequisites

### Required Tools

```bash
# Install uv (recommended package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or install with pip
pip install uv

# Alternative: use pip and twine directly
pip install build twine
```

### Python Version Support

- Minimum Python 3.8+ recommended
- Specify supported versions in `pyproject.toml`
- Test on multiple Python versions before publishing

## Package Preparation

### 1. Project Structure

```
your-package/
├── src/
│   └── your_package/
│       ├── __init__.py
│       ├── py.typed          # For type hints
│       └── your_modules.py
├── tests/
│   └── test_*.py
├── examples/
│   └── usage_examples.py
├── pyproject.toml            # Main configuration
├── README.md                 # Package documentation
├── LICENSE                   # License file
├── CHANGELOG.md              # Version history (optional)
└── .gitignore
```

### 2. Configure pyproject.toml

Create a comprehensive `pyproject.toml`:

```toml
[project]
name = "your-package-name"
version = "0.1.0"
description = "Short description of your package"
readme = "README.md"
license = { text = "MIT" }
authors = [
    { name = "Your Name", email = "your.email@example.com" }
]
maintainers = [
    { name = "Your Name", email = "your.email@example.com" }
]
requires-python = ">=3.8"
dependencies = [
    "dependency1>=1.0.0",
    "dependency2>=2.0.0,<3.0.0",
]
keywords = [
    "keyword1",
    "keyword2", 
    "relevant-tags"
]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Software Development :: Libraries :: Python Modules",
    "Typing :: Typed",
]

[project.urls]
Homepage = "https://github.com/username/your-package"
Documentation = "https://github.com/username/your-package#readme"
Repository = "https://github.com/username/your-package.git"
"Bug Tracker" = "https://github.com/username/your-package/issues"
Changelog = "https://github.com/username/your-package/releases"

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
    "mypy>=1.0.0",
]
docs = [
    "sphinx>=5.0.0",
    "sphinx-rtd-theme>=1.0.0",
]
all = ["your-package[dev,docs]"]

[project.scripts]
your-cli-command = "your_package.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.uv]
dev-dependencies = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
    "mypy>=1.0.0",
    "twine>=6.0.0",
]

[tool.hatch.build.targets.wheel]
packages = ["src/your_package"]

[tool.black]
line-length = 88
target-version = ['py38']

[tool.ruff]
target-version = "py38"
line-length = 88

[tool.mypy]
python_version = "3.8"
strict = true
```

### 3. Create Essential Files

#### LICENSE (MIT Example)

```text
MIT License

Copyright (c) 2025 Your Name

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

#### README.md Template

```markdown
# Your Package Name

Brief description of what your package does.

## Features

- Feature 1
- Feature 2
- Feature 3

## Installation

```bash
pip install your-package-name
```

## Quick Start

```python
from your_package import main_class

# Example usage
instance = main_class()
result = instance.do_something()
```

## Documentation

Full documentation available at [link-to-docs]

## Contributing

Contributions welcome! Please read our contributing guidelines.

## License

This project is licensed under the MIT License - see LICENSE file for details.
```

#### py.typed (for type hints)

Create an empty file `src/your_package/py.typed` to indicate your package supports type hints.

## PyPI Account Setup

### 1. Create Accounts

- **Production PyPI**: https://pypi.org/account/register/
- **Test PyPI** (recommended for testing): https://test.pypi.org/account/register/

### 2. Generate API Tokens

1. Go to PyPI Account Settings → API tokens
2. Click "Add API token"
3. Set scope to "Entire account" or specific project
4. Copy the token (starts with `pypi-`)

### 3. Configure Authentication

#### Option A: Environment Variables

```bash
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-your-api-token-here
```

#### Option B: .pypirc File

Create `~/.pypirc`:

```ini
[distutils]
index-servers = pypi testpypi

[pypi]
username = __token__
password = pypi-your-production-token-here

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-your-test-token-here
```

Set proper permissions:
```bash
chmod 600 ~/.pypirc
```

## Publishing Methods

### Method 1: Using uv (Recommended)

```bash
# Install development dependencies
uv sync --all-extras

# Run tests
uv run pytest

# Format and lint code
uv run black .
uv run ruff check .

# Build the package
uv build

# Check the distribution
uv run twine check dist/*

# Upload to TestPyPI first (recommended)
uv run twine upload --repository testpypi dist/*

# Test installation from TestPyPI
pip install --index-url https://test.pypi.org/simple/ your-package-name

# Upload to production PyPI
uv run twine upload dist/*
```

### Method 2: Using Traditional Tools

```bash
# Install build tools
pip install build twine

# Build the package
python -m build

# Check the distribution
twine check dist/*

# Upload to TestPyPI
twine upload --repository testpypi dist/*

# Upload to PyPI
twine upload dist/*
```

### Method 3: Direct Upload (Advanced)

```bash
# Build and upload in one step
uv run twine upload --repository pypi dist/*

# With custom repository URL
uv run twine upload --repository-url https://upload.pypi.org/legacy/ dist/*
```

## Testing and Verification

### 1. Pre-Publication Checks

```bash
# Verify package builds
uv build

# Check package metadata and files
uv run twine check dist/*

# Test installation locally
pip install dist/*.whl

# Run your package tests
python -c "import your_package; print('Import successful!')"
```

### 2. TestPyPI Testing

```bash
# Upload to TestPyPI
uv run twine upload --repository testpypi dist/*

# Install from TestPyPI
pip install --index-url https://test.pypi.org/simple/ your-package-name

# Test functionality
python -c "from your_package import YourClass; YourClass().test_method()"
```

### 3. Post-Publication Verification

```bash
# Install from production PyPI
pip install your-package-name

# Verify on different Python versions
python3.8 -c "import your_package"
python3.9 -c "import your_package"
python3.10 -c "import your_package"
python3.11 -c "import your_package"
python3.12 -c "import your_package"
```

## Troubleshooting

### Common Errors and Solutions

#### 1. "Package already exists"

```bash
# Update version in pyproject.toml, then rebuild
uv build
uv run twine upload dist/*
```

#### 2. "Invalid authentication credentials"

```bash
# Regenerate API token and update .pypirc or environment variables
# Ensure username is "__token__" not your username
```

#### 3. "File already exists"

```bash
# Clean old distributions
rm -rf dist/
uv build
uv run twine upload dist/*
```

#### 4. "Invalid classifier"

Check PyPI classifiers list: https://pypi.org/classifiers/

#### 5. "README rendering issues"

```bash
# Test README rendering
uv run twine check dist/*

# Validate markdown
python -c "import readme_renderer.markdown; print('OK')"
```

### Debugging Commands

```bash
# Verbose upload
uv run twine upload --verbose dist/*

# Check package contents
tar -tzf dist/*.tar.gz
unzip -l dist/*.whl

# Validate metadata
python -m build --outdir dist/ .
python -c "import pkginfo; print(pkginfo.get_metadata('dist/*.whl'))"
```

## Best Practices

### 1. Version Management

```bash
# Use semantic versioning (MAJOR.MINOR.PATCH)
# 0.1.0 → 0.1.1 (patch - bug fixes)
# 0.1.1 → 0.2.0 (minor - new features)
# 0.2.0 → 1.0.0 (major - breaking changes)
```

### 2. Package Naming

- Use lowercase letters, numbers, and hyphens
- Avoid underscores (use hyphens instead)
- Make it descriptive and unique
- Check availability on PyPI first

### 3. Documentation

```bash
# Include comprehensive README
# Add docstrings to all public functions
# Provide usage examples
# Document breaking changes in CHANGELOG.md
```

### 4. Testing Strategy

```bash
# Test on multiple Python versions
# Test installation from both TestPyPI and PyPI
# Include comprehensive test suite
# Test optional dependencies separately
```

### 5. Security

```bash
# Never commit API tokens to version control
# Use environment variables or .pypirc
# Enable 2FA on PyPI account
# Regularly rotate API tokens
```

## Automation and CI/CD

### GitHub Actions Workflow

Create `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  build-and-publish:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install uv
      uses: astral-sh/setup-uv@v2
    
    - name: Install dependencies
      run: uv sync --all-extras
    
    - name: Run tests
      run: uv run pytest
    
    - name: Build package
      run: uv build
    
    - name: Check distribution
      run: uv run twine check dist/*
    
    - name: Publish to PyPI
      env:
        TWINE_USERNAME: __token__
        TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
      run: uv run twine upload dist/*
```

### Release Process

```bash
# 1. Update version in pyproject.toml
# 2. Update CHANGELOG.md
# 3. Commit changes
git add .
git commit -m "Release v1.0.0"

# 4. Create and push tag
git tag v1.0.0
git push origin main --tags

# 5. Create GitHub release (triggers CI/CD)
# 6. Verify package on PyPI
```

### Manual Release Script

Create `scripts/release.sh`:

```bash
#!/bin/bash
set -e

VERSION=$1
if [ -z "$VERSION" ]; then
    echo "Usage: $0 <version>"
    exit 1
fi

echo "Preparing release $VERSION..."

# Update version in pyproject.toml
sed -i "s/version = \".*\"/version = \"$VERSION\"/" pyproject.toml

# Run tests
uv run pytest

# Build package
uv build

# Check distribution
uv run twine check dist/*

# Create git tag
git add pyproject.toml
git commit -m "Release v$VERSION"
git tag "v$VERSION"

# Upload to PyPI
uv run twine upload dist/*

# Push to git
git push origin main --tags

echo "Release $VERSION published successfully!"
```

## Advanced Topics

### 1. Multi-file Packages

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/package1", "src/package2"]
```

### 2. Binary Extensions

```toml
[build-system]
requires = ["setuptools", "wheel", "Cython"]
build-backend = "setuptools.build_meta"
```

### 3. Namespace Packages

```python
# src/namespace/package/__init__.py
__path__ = __import__('pkgutil').extend_path(__path__, __name__)
```

### 4. Entry Points and Scripts

```toml
[project.scripts]
my-cli = "my_package.cli:main"

[project.entry-points."my_package.plugins"]
plugin1 = "my_package.plugins:plugin1"
```

This comprehensive guide should cover everything you need to know about publishing Python packages to PyPI. Keep it as a reference for all your future package publishing needs!