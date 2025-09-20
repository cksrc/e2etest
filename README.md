# MPT AI E2E Tester

This tool is used to test the MPT AI platform with end-to-end automated scenarios.
It supports both interactive and headless modes for different testing needs.

## Features

- **Interactive Mode**: Step-by-step execution with user confirmation and visible browser
- **Headless Mode**: Automated execution with report generation
- **Mock Voice Manager**: Built-in mock server for testing websocket communication

## Quick Start

### 1. Install Dependencies

Using uv (recommended):

```bash
uv pip install -e ".[dev]"
```

Or using pip:

```bash
pip install websockets python-dotenv pytest pytest-asyncio ruff
```

### 2. Configure Environment

Copy the example environment file and customize:

```bash
cp .env.example .env
```

Edit `.env` to set your voice manager configuration:

```bash
VOICE_MANAGER_IP=localhost
VOICE_MANAGER_PORT=8070
USER_ID=your_user_id
```

### 3. Run the CLI

```bash
python main.py
```

### 3. Test with Mock Voice Manager

Start the mock voice manager server:

```bash
python mock_voice_manager.py
```

In another terminal, test the connection:

```bash
python test_voice_client.py
```

## Mock Voice Manager

The mock voice manager simulates the real voice manager for testing purposes.

### Message Protocol

1. **Initial Connection**: Send UID registration

   ```json
   { "UID": "user_id_here" }
   ```

2. **User Messages**: Send user prompts

   ```json
   { "USER": "user prompt goes here" }
   ```

3. **LLM Responses**: Receive responses
   ```json
   { "LLM": "Response from LLM" }
   ```

### Configuration

The voice manager IP and port are configurable in `config.yaml`:

```yaml
VOICE_MANAGER_IP: 10.100.128.235
VOICE_MANAGER_PORT: 8070
```

## Development

### Setup Development Environment

1. **Install development dependencies:**

   ```bash
   # Using Python task runner (recommended)
   python tasks.py install-dev

   # Or using make (if you prefer)
   make install-dev
   ```

2. **Set up environment file:**

   ```bash
   # Using Python task runner
   python tasks.py setup-env

   # Or using make
   make setup-env
   ```

### Development Commands

- **Run tests:**

  ```bash
  # Python task runner (recommended)
  python tasks.py test              # Run all tests
  python tasks.py test-cov          # Run tests with coverage
  python tasks.py test-unit         # Run only unit tests
  python tasks.py test-integration  # Run only integration tests

  # Or using make
  make test test-cov test-unit test-integration
  ```

- **Code quality:**

  ```bash
  # Python task runner
  python tasks.py lint              # Check code with ruff
  python tasks.py format            # Format code with ruff
  python tasks.py check             # Run all checks (lint + test)

  # Or using make
  make lint format check
  ```

- **Development servers:**

  ```bash
  # Python task runner
  python tasks.py run-mock          # Start mock voice manager
  python tasks.py run-cli           # Start the CLI

  # Or using make
  make run-mock run-cli
  ```

- **Cleanup:**

  ```bash
  # Python task runner
  python tasks.py clean             # Remove generated files

  # Or using make
  make clean
  ```

### Testing

The project uses pytest for testing with the following structure:

- **Unit tests**: Fast tests that don't require external dependencies
- **Integration tests**: Tests that require running services (marked with `@pytest.mark.integration`)
- **Slow tests**: Long-running tests (marked with `@pytest.mark.slow`)

Run specific test categories:

```bash
pytest -m "unit"           # Only unit tests
pytest -m "integration"    # Only integration tests
pytest -m "not slow"       # Skip slow tests
```

### Code Quality

The project uses:

- **Ruff**: For linting and code formatting
- **pytest**: For testing with async support
- **Coverage**: For test coverage reporting

All code is automatically formatted and linted in CI/CD.
