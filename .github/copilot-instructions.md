# GitHub Copilot Project Instructions

## 1. Code Reuse & DRY Principle (CRITICAL)
- **Search Before Coding:** Before generating any new features or logic, prioritize searching the existing codebase, specifically the `src/roly/`  directories.
- **Avoid Duplication:** Do not reimplement existing logic. If a helper function or utility exists, import and reuse it.
- **Refactor Over Duplicate:** If an existing function provides similar logic but needs slight modification to support a new feature, suggest refactoring the existing code rather than creating a redundant version.

## 2. Unit Testing & Quality Assurance
- **Mandatory Test Cases:** For every new feature or logic change, you must provide corresponding unit test cases.
- **Framework Consistency:** Use the project's existing testing framework `pytest`. Check the `tests/unit` directory for established patterns.
- **Mocking:** Use standard mocking libraries (like `unittest.mock` or `pytest-mock`) to isolate external dependencies (APIs, Databases) in tests.
- **Test Placement:** Ensure new tests are placed in the appropriate location within the `tests/` folder, following the existing naming convention (e.g., `test_*.py`).

## 3. Project Context & Architecture

- **Architecture Awareness:** Analyze the existing project structure (e.g., Typer) before proposing changes. Ensure new code aligns with the established architectural patterns.
- **Dependency Management:** Stick to the libraries already defined in `pyproject.toml`. Avoid introducing new dependencies unless explicitly requested.

## 4. Coding Standards & Style

- **Naming Conventions:** Follow the variable, function, and class naming conventions already present in the codebase.
- **Type Hinting:** Use Python type hints for all function signatures and complex variables to maintain type safety.
- **Documentation:** Provide docstrings for new functions that match the style (Sphinx) used in the current project.

## 5. Execution Workflow

- **Plan First:** For complex features, provide a brief execution plan or summary of which files will be modified and which existing functions will be reused before generating the full code block.
- **File Paths:** Always specify the suggested file path for new code based on the current directory structure.

## 6. Project Folder Map

### Key Directories Summary

| Directory | Purpose |
|-----------|---------|
| `src/roly/` | Core library code for test execution and validation |
| `src/roly/cli/` | Command-line interface using Typer framework |
| `src/roly/plugins/` | Ansible plugin extensions (callbacks and modules) |
| `src/roly/runner/` | Test execution engines (local and Docker) |
| `tests/unit/` | Unit tests for core functionality |
| `tests/integration/` | Integration tests validating plugin behavior |
| `tests/test_callback_plugin/` | Test fixtures in YAML format |

### Key Files Summary

| File | Purpose |
|------|---------|
| `ansible.py` | Orchestrates Ansible playbook execution and integration |
| `test_case.py` | Defines test case structure and lifecycle |
| `assert_check.py` | Validates task outputs against expected assertions |
| `runner.py` | Abstract base for test execution strategies |
| `roly_callback.py` | Ansible callback plugin that captures test results |
| `roly_assert.py` | Ansible module for inline assertions |
| `roly_mock.py` | Ansible module for service mocking |
| `config.py` | Loads and manages configuration from YAML |
| `report.py` | Generates test execution reports |
