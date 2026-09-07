# Contributing to LXC AutoScale

Thank you for your interest in contributing to LXC AutoScale! We welcome contributions from the community, whether it's bug reports, feature requests, documentation improvements, or code contributions.

## How to Contribute

### Reporting Issues

If you encounter a bug or have a feature request:

1. Check if the issue already exists in the [issue tracker](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/issues)
2. If not, [create a new issue](https://github.com/fabriziosalmi/proxmox-lxc-autoscale/issues/new/choose)
3. Provide a clear description, steps to reproduce (for bugs), and any relevant logs or configuration

### Submitting Pull Requests

We appreciate code contributions! To submit a pull request:

1. **Fork the repository** and create a new branch from `main`
   ```bash
   git checkout -b feature/your-feature-name
   ```
   or
   ```bash
   git checkout -b fix/your-bug-fix
   ```

2. **Make your changes** following these guidelines:
   - Write clear, concise commit messages
   - Follow the existing code style and conventions
   - Add comments for complex logic
   - Update documentation if you change functionality

3. **Test your changes** thoroughly:
   - Ensure the service starts and stops correctly
   - Test scaling operations with your changes
   - Verify configuration changes work as expected

4. **Submit your pull request**:
   - Provide a clear description of the changes
   - Reference any related issues (e.g., "Fixes #123")
   - Ensure all tests pass (if applicable)

### Branch Naming Convention

Use descriptive branch names:
- `feature/` - for new features
- `fix/` - for bug fixes
- `docs/` - for documentation changes
- `refactor/` - for code refactoring

### Code Style

- Follow PEP 8 guidelines for Python code
- Use meaningful variable and function names
- Keep functions focused and single-purpose
- Add docstrings to functions and classes

### Testing

Before submitting a pull request:

1. Test the installation process
2. Verify the service runs correctly
3. Test scaling operations with various configurations
4. Check that logging works as expected

### Documentation

If your contribution changes functionality:

- Update the relevant documentation in `docs/`
- Update the main `README.md` if necessary
- Add examples for new features
- Update configuration examples if needed

## Development Setup

To set up a development environment:

1. Clone the repository:
   ```bash
   git clone https://github.com/fabriziosalmi/proxmox-lxc-autoscale.git
   cd proxmox-lxc-autoscale
   ```

2. Install dependencies:
   ```bash
   pip install -r lxc_autoscale/requirements.txt
   ```

3. Make your changes and test them locally

## Checking a change against a real node

The unit suite mocks `run_command`. Every defect that has reached users in this
project lived on the other side of that mock: a sysfs attribute that does not
exist, a config path the hypervisor resolves through a symlink, page cache and
then shared memory counted wrongly, a snapshot never cleaned up. A green suite
has never been evidence that the daemon does the right thing on a host.

`scripts/live-check.py` runs the daemon against a real Proxmox node and asserts
what actually happened to the cgroups and to the container configuration:

```bash
sudo ./scripts/live-check.py --yes-i-understand-this-creates-a-container
```

Run it on the node, from a checkout, as root. It creates one throwaway
container, runs the daemon against it for a few cycles, and exits non-zero if a
check fails.

It is safe to run on a node with real guests on it, by construction:

- every pre-existing guest is placed in `ignore_lxc`, and the daemon's own view
  is asserted to contain only the throwaway container before anything starts;
- the checksum of every pre-existing container config is taken first and
  compared at the end, and a difference fails the run;
- the daemon is pointed at a config in a temporary directory through
  `LXC_AUTOSCALE_CONFIG`, so the node's own configuration is never written;
- the daemon is never installed as a service and every run has a timeout;
- teardown runs even when a check fails.

Each check corresponds to a defect that shipped. If you change how usage is
measured, how the container config is written, or the lifecycle of snapshots and
boosts, run this before opening the pull request and paste the output into it.

A check that cannot fail is worth nothing, so verify the harness has teeth the
same way: reintroduce the defect the check describes, confirm it fails, then put
the code back.

## Questions?

If you have questions about contributing, feel free to:
- Open an issue for discussion
- Reach out via the community channels

Thank you for helping improve LXC AutoScale!
