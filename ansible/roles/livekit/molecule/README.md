# LiveKit Role Testing

This directory contains Molecule tests for the LiveKit Ansible role.

## Prerequisites

Install the required testing tools:

```bash
pip install molecule molecule-plugins[docker] ansible-core ansible-lint
```

## Running Tests

### Full Test Suite

Run the complete test lifecycle:

```bash
cd ansible/roles/livekit
molecule test
```

This will:

1. Create a Docker container
1. Apply the LiveKit role
1. Run idempotency tests
1. Verify the service is running correctly
1. Clean up

### Individual Steps

```bash
molecule create    # Create test instances
molecule converge  # Apply the role
molecule verify    # Run verification tests
molecule idempotence  # Test idempotency
molecule destroy   # Clean up
```

### Run with Specific Platform

```bash
molecule test -- --limit ubuntu2404
```

## Test Scenarios

### Default Scenario

The default scenario tests:

- LiveKit service installation and startup
- Configuration file creation with correct permissions
- Livekit-jwt service installation and startup
- Nginx configuration and startup
- API endpoint accessibility

### Custom Scenarios

You can create additional scenarios in `molecule/` directories for different configurations (e.g., with TURN enabled, different ports, etc.).

## CI Integration

The Molecule tests are designed to run in CI pipelines. See the GitHub Actions workflow example in the main repository documentation.

## Troubleshooting

### Docker Permission Issues

If you encounter permission issues with Docker, ensure your user is in the `docker` group:

```bash
sudo usermod -aG docker $USER
```

### Container Startup Failures

If containers fail to start, check that systemd is properly configured:

```bash
molecule test -s default -- --vvv
```

### Verbose Output

For debugging, add verbose flags:

```bash
molecule converge -- --vvv
```
