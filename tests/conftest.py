import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(f"script_{name}", ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def analyse_script():
    return _load_script("analyse")


@pytest.fixture(scope="session")
def pull_script():
    return _load_script("pull")


# Public copy (PUBLIC.md): tests that need files this copy leaves out are skipped here, with that
# reason; they run in full in the private repository.
def pytest_collection_modifyitems(config, items):
    import pathlib
    import pytest
    listed = pathlib.Path(__file__).with_name("public_skip.txt")
    skip = set(listed.read_text(encoding="utf-8").split()) if listed.exists() else set()
    for item in items:
        if item.nodeid in skip or item.nodeid.split("[")[0] in skip or item.nodeid.split("::")[0] in skip:
            item.add_marker(pytest.mark.skip(reason="needs files this public copy leaves out (PUBLIC.md)"))
