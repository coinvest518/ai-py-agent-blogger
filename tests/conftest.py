import os
import pytest


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


def pytest_addoption(parser):
    parser.addoption(
        "--run-all-tests",
        action="store_true",
        default=False,
        help="Run the full test suite (default: only run E2E tests)"
    )


def pytest_collection_modifyitems(config, items):
    """Default test selection: run only end-to-end tests named `test_e2e_*` or marked `e2e`.

    This preserves existing test files but keeps CI/dev focus on the single E2E flow
    the team asked for. Use `--run-all-tests` or set `RUN_ALL_TESTS=1` to run everything.
    """
    run_all = config.getoption("--run-all-tests") or os.getenv("RUN_ALL_TESTS") == "1"
    if run_all:
        return

    selected = []
    deselected = []
    for item in items:
        # keep tests explicitly marked 'e2e' or files starting with test_e2e_
        if item.get_closest_marker("e2e") is not None or item.name.startswith("test_e2e_"):
            selected.append(item)
        else:
            deselected.append(item)

    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = selected
