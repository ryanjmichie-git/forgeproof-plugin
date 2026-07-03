"""Pytest configuration for the ForgeProof engine test suite."""


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: exercises the real ssh-keygen signing path"
    )
