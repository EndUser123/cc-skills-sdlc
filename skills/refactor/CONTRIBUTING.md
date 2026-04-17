# Contributing to refactor

First off, thanks for taking the time to contribute!

## Development Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/refactor.git
cd refactor

# Install dependencies (if applicable)
pip install -e .

# Run tests
pytest tests/ -v
```

## Code Style

- Follow existing code conventions
- Use type hints for all functions
- Add docstrings for public APIs
- Keep functions focused and small

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=scripts --cov-report=term-missing
```

## Submitting Changes

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Pull Request Guidelines

- Describe your changes in the PR description
- Include screenshots for UI changes
- Link to related issues
- Ensure all tests pass
- Add tests for new functionality

## Reporting Issues

Use the GitHub issue tracker and include:
- Clear description of the problem
- Steps to reproduce
- Expected behavior
- Actual behavior
- Environment details
