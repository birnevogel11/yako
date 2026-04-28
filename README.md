# Yako

A mock-based testing framework for Ansible playbooks and roles. Yako intercepts task execution via an Ansible callback plugin to inject mocks and run assertions, enabling unit-style testing without real infrastructure.

Inspired by [Monkeyble](https://github.com/HewlettPackard/monkeyble), with key differences:

- Each test case can run in an isolated Docker container
- Hierarchical configuration (global → module → test case)
- Built-in `yako_assert` module for inline assertions inside playbooks

## Running Yako

Requires Python 3.12+.

Run Yako directly without installing it globally:

```shell
uvx yako test
```

If you are working inside a checkout of this repository, run the local code with:

```shell
uv sync
uv run yako test
```

## Development

For local development, sync the project environment and include the `dev` dependency group
defined in `pyproject.toml`:

```shell
uv sync --group dev
```

After that, run the local checkout and development tools with `uv run`:

```shell
# Run all Python tests
uv run pytest

# Run Yako itself from the local checkout
uv run yako test
```

## Quick Start

### 1. Create a configuration file

Create `yako.yaml` in your repository root:

```yaml
runner_mode: "local"
```

### 2. Write a test case

Create `tests/yako/test_hello.yaml`:

```yaml
test_cases:
  - name: "test_hello"
    tasks:
      - name: Say hello
        debug:
          msg: "Hello, world!"
```

### 3. Run

```shell
# Run without installing globally
uvx yako test

# Or run the local checkout
uv run yako test
```

## Writing Test Cases

Test files are YAML files named `test_*.yaml`, placed under `tests/yako/` by default. Each file is a **test module** containing one or more **test cases**.

```yaml
# Module-level given (applies to all test cases in this file)
given:
  vars:
    env: "testing"

test_cases:
  - name: "test_something"
    given:
      vars:
        feature_flag: true
      state:
        - task: "Install packages"
          mock: {}
    tasks:
      - name: Say hello
        debug:
          msg: "Hello, world!"
```

Files can include other files or urls by using the `!inc <path|url>` tag.

```yaml
# Module-level given (applies to all test cases in this file)
given: !inc global_given.yaml

test_cases:
  - name: "test_something"
    given:
      vars: !inc /opt/system/vars.yaml
      state:
        - task: "Install packages"
          mock: !inv https://github.com/path/to/my-mock.yaml
    tasks:
      - name: Say hello
        debug:
          msg: "Hello, world!"
```

### Playbooks vs Inline Tasks

Each test case must specify either `playbooks` or `tasks`, not both.

**Reference an existing playbook:**

```yaml
test_cases:
  - name: "test_with_playbook"
    playbooks:
      - "my_playbook.yaml"
```

Playbook search paths (in order):
1. `<test_file_dir>/playbooks/`
2. `<base_dir>/playbooks/`
3. Repository-level playbook paths from config

**Define inline tasks directly:**

```yaml
test_cases:
  - name: "test_with_inline_tasks"
    tasks:
      - name: Set a variable
        set_fact:
          my_var: "hello"
      - name: Verify variable
        yako_assert:
          stmts:
            - actual: "{{ my_var }}"
              expected: "hello"
```

### Directory Structure

```
tests/yako/
├── test_basic.yaml              # Simple: tests + playbooks together
├── playbooks/
│   └── shared_playbook.yaml
├── files/
│   └── test_data.txt
└── my_role_tests/               # Nested: organized by topic
    ├── test_install.yaml
    ├── playbooks/
    │   └── install.yaml
    └── files/
        └── config.ini
```

## Given: Test Setup

The `given` block configures the test environment. It can be defined at three levels, which merge together (global → module → test case):

- **`files`** and **`state`**: concatenated across levels
- **`vars`**: merged as a dict (more specific level wins)

### Extra Variables

Inject Ansible variables into the playbook run:

```yaml
given:
  vars:
    target_user: "deploy"
    packages:
      - nginx
      - curl
```

### Copying Files

Place files into the test workspace before execution:

```yaml
given:
  files:
    # Simple: copies file with same name
    - "config.ini"

    # Explicit source and destination
    - src: "fixtures/config.ini"
      dest: "config.ini"

    # Absolute destination path
    - src: "hosts.txt"
      dest: "/tmp/hosts.txt"

    # Jinja2 template in destination
    - src: "data.txt"
      dest: "{{ target_dir }}/data.txt"

    # Copy a directory (trailing slash)
    - "test_data/"
```

Files are resolved from `files/` directories adjacent to the test file or in the base directory.

## Mocking Tasks

Mock tasks by matching their **name** exactly. When Ansible reaches a mocked task, yako's callback plugin intercepts it and replaces the real execution.

### Basic Mock

Prevent a task from running without specifying any result:

```yaml
given:
  state:
    - task: "Install packages"
      mock: {}
```

### Mock with Results

Return specific values from the mocked task:

```yaml
given:
  state:
    - task: "Create temp file"
      mock:
        changed: true
        result_dict:
          path: "/tmp/fake_file"
```

Variables from `result_dict` are available to subsequent tasks via `register`.

### Mock with Custom Action

Replace a task's module with a different one entirely:

```yaml
given:
  state:
    - task: "Create temp file"
      mock:
        custom_action:
          set_fact:
            temp_path: "/tmp/fake"
```

### Per-Task Extra Variables

Inject variables that are only available during a specific task:

```yaml
given:
  state:
    - task: "Deploy application"
      vars:
        deploy_version: "1.2.3"
      mock: {}
```

## Assertions

### Callback Assertions: assert_inputs / assert_outputs

Assert on variables **before** (`assert_inputs`) or **after** (`assert_outputs`) a mocked task runs:

```yaml
given:
  state:
    - task: "Deploy to server"
      mock: {}
      assert_inputs:
        - name: "target_host"
          value: "prod-01"
        - name: "deploy_version"
          value: "1.0"
          mode: "!="
      assert_outputs:
        - name: "result.path"
          value: "/opt/app"
```

### Inline Assertions: yako_assert Module

Use the `yako_assert` Ansible module inside tasks for assertions at any point in a playbook:

```yaml
tasks:
  - name: Set variables
    set_fact:
      count: 5
      items: [1, 2, 3]

  - name: Verify results
    yako_assert:
      stmts:
        - actual: "{{ count }}"
          expected: 5
          mode: ">"
          msg: "Count should be greater than 5"

        - actual: "{{ items }}"
          mode: "is_not_none"
```

### Assertion Modes

| Mode | Description |
|------|-------------|
| `==` | Equal (default) |
| `!=` | Not equal |
| `<` | Less than |
| `>` | Greater than |
| `<=` | Less than or equal |
| `>=` | Greater than or equal |
| `in` | Value is in collection |
| `not_in` | Value is not in collection |
| `is_none` | Value is None |
| `is_not_none` | Value is not None |
| `is_true` | Value is truthy |
| `is_false` | Value is falsy |
| `is_not_true` | Value is not truthy |
| `is_not_false` | Value is not falsy |

### State Checks

Verify task behavior without checking specific values:

```yaml
given:
  state:
    - task: "Conditional task"
      should_be_skipped: true    # Assert the task was skipped
      mock: {}

    - task: "Modify config"
      should_be_changed: true    # Assert the task reported changed
      mock:
        changed: true

    - task: "Bad input handler"
      should_fail: true          # Assert the task failed
      mock: {}
```

## Parametrization

Run the same test case with different inputs:

```yaml
test_cases:
  - name: "test_deploy"
    tasks:
      - name: Deploy
        debug:
          msg: "Deploying to {{ target_env }}"

    parametrize:
      staging:
        vars:
          target_env: "staging"
      production:
        vars:
          target_env: "production"
```

This creates two test cases:
- `test_deploy.yaml::test_deploy[staging]`
- `test_deploy.yaml::test_deploy[production]`

Each variant can override `vars`, `files`, and `state`.

## Configuration

Yako loads configuration from `yako.yaml` (and optionally `yako_local.yaml`) in the repository root.

### Runner Mode

```yaml
runner_mode: "local"   # or "docker"
```

- **`local`** — Runs ansible-playbook directly on the host
- **`docker`** — Runs each test case in a fresh Docker container

### Ansible Settings

Use the top-level `ansible` block for settings shared by both runner modes. Yako resolves
`roles_path` before each test run and writes the resulting paths into a generated
`ansible.cfg`, so the playbook under test can import local roles and roles from Git
repositories.

- `roles_path` accepts either local paths or `{ repo, path }` entries
- `repo_staging` maps a Git URL to an existing local checkout instead of using the cache
- unresolved Git repos are cloned into Yako's cache under `~/.cache/yako/repos/`
- `ansible_playbook` controls the generated `ansible-playbook` invocation
- `runner.local.ansible` and `runner.docker.ansible` are merged with this block for the
  selected runner, so you can keep shared defaults at the top level and add runner-specific
  overrides when needed

`ansible_playbook.connection`, `inventory`, `limit`, and `ansible_stdout_callback` map
directly to the generated command and environment. Use `extra_args` for additional flags
such as `--diff`, `--check`, or `-vvv`.

```yaml
ansible:
  roles_path:
    # Local path
    - "roles/"
    # Git repository (cloned and cached automatically)
    - repo: "https://github.com/org/ansible-roles.git"
      path: "roles"

  # Reuse a local checkout instead of cloning the repo into the cache
  repo_staging:
    "https://github.com/org/ansible-roles.git": "../ansible-roles"

  ansible_playbook:
    connection: local
    inventory: "127.0.0.1,"
    limit: "127.0.0.1"
    ansible_stdout_callback: "debug"
    extra_args:
      - "--diff"
```

### Docker Runner

Use `runner.docker` when you want every test case to run inside a fresh container. The
defaults match this repository's `Dockerfile`, which places the virtual environment in
`/home/ubuntu/app` and the Yako source tree in `/home/ubuntu/yako`.

When the Docker runner starts, Yako automatically bind-mounts:

- resolved role paths
- the base test directories and discovered playbook directories
- the generated temporary workspace for the current test case
- the directory containing the test file, so adjacent `files/` content remains available

Important fields:

- `image_name` selects the container image to run
- `workspace_dir` is the in-container temp workspace used for generated playbooks and test
  case config
- `yako_venv_dir` tells Yako where to find `ansible-playbook` inside the image
- `yako_src_dir` is used to generate `ansible.cfg` entries for Yako's callback and module
  plugins inside the container
- `extra_args` is appended to `docker container run`
- `host_yako_repo_dir` optionally mounts your local Yako checkout at `/home/ubuntu/yako`,
  which is useful when developing Yako itself and testing the current source tree inside
  the container

You can also add Docker-only Ansible settings under `runner.docker.ansible`; they are
merged with the top-level `ansible` block when `runner_mode: "docker"` is active.

The published GHCR image at `ghcr.io/birnevogel11/yako` is a multi-platform manifest
list for `linux/amd64` and `linux/arm64/v8`. The `latest` tag tracks the default
branch, and Git tags publish matching semver image tags.

```yaml
runner:
  docker:
    image_name: "ghcr.io/birnevogel11/yako:latest"
    workspace_dir: "/home/ubuntu/workspace"
    yako_venv_dir: "/home/ubuntu/app"
    yako_src_dir: "/home/ubuntu/yako/src/yako"
    extra_args:
      - "--user=1000:1000"
    host_yako_repo_dir: "."    # Mount local yako source for Yako development
    ansible:
      ansible_playbook:
        extra_args:
          - "--check"
```

### Global Given

Define defaults that apply to **all** test cases:

```yaml
given:
  vars:
    ansible_os_family: "Debian"
  state:
    - task: "Gather facts"
      mock: {}
```

## CLI Usage

Examples below use `uvx yako` so you can run Yako without installing it. When developing inside this repository, replace `uvx yako` with `uv run yako`.

```shell
# Run all tests
uvx yako test

# Run tests in specific directories
uvx yako test tests/yako/networking/ tests/yako/storage/

# Filter tests by name
uvx yako test --filter-key "test_deploy"

# Verbose output
uvx yako test -v

# Custom config file
uvx yako test -c custom_yako.yaml
```

## License

Yako is licensed under the GNU General Public License v3.0. See `LICENSE` for the
full text.
