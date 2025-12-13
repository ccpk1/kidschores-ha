# KidsChores Integration Test Suite

This directory contains all automated tests for the KidsChores Home Assistant integration. The tests ensure the integration's reliability, correct behavior, and compatibility with Home Assistant's requirements.

## Test Organization

- **test_config_flow.py**: Tests the multi-step configuration flow (setup via UI)
- **test_options_flow.py**: Tests the options flow (editing integration settings)
- **test_coordinator.py**: Tests core business logic, entity lifecycle, and points/badges/rewards
- **test_services.py**: Tests Home Assistant service calls (claim, approve, bonus, penalty, etc.)
- **conftest.py**: Shared fixtures and helpers for all tests

## Running the Tests

You can run all tests from the root of the repository or from this directory:

```sh
# Run all tests with verbose output
python -m pytest tests/ -v

# Run only a specific test file
python -m pytest tests/test_config_flow.py

# Run with short tracebacks (default)
python -m pytest tests/
```

## Linting

All test files are checked with pylint and must have a perfect score (10.00/10):

```sh
python -m pylint tests/*.py --disable=duplicate-code,too-many-statements
```

## Guidelines

- All test code must be type-annotated and pass both pytest and pylint with no errors or warnings.
- Use fixtures from `conftest.py` for setup and mocking.
- Access to protected members (e.g., `_create_kid`) is allowed in tests and suppressed with `# pylint: disable=protected-access`.
- Use the `.get()` method for TypedDict access to avoid type checker errors.

## Example: Adding a New Test

1. Create a new function in the appropriate test file, starting with `test_`.
2. Use fixtures for setup (see `conftest.py`).
3. Assert expected behavior using `assert` statements.
4. Run the tests and ensure all pass.

## Example: Running a Single Test Function

```sh
python -m pytest tests/test_services.py -k test_service_apply_bonus_and_penalty
```

## More Information

- See the main repository README for integration details.
- For Home Assistant test best practices, see the [Home Assistant developer docs](https://developers.home-assistant.io/docs/development_testing/).
