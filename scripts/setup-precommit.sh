#!/bin/bash

# Setup pre-commit hooks
echo "Setting up pre-commit hooks..."

# Install pre-commit if not installed
if ! command -v pre-commit &> /dev/null; then
    echo "Installing pre-commit..."
    pip install pre-commit
fi

# Install pre-commit hooks
pre-commit install

echo "✓ Pre-commit hooks installed successfully"
echo ""
echo "Hooks configured:"
echo "  - Backend: ruff (linting + formatting)"
echo "  - Frontend: eslint + prettier"
echo "  - General: trailing whitespace, YAML checks, etc."
echo ""
echo "Run 'pre-commit run --all-files' to test all hooks"
