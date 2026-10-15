from pathlib import Path
from uuid import uuid4

import pytest

from faultglass.context_config import ContextConfig
from faultglass.execution import run_case
from faultglass.graph_repository import GraphRepository
from faultglass.models import read_case

FIXTURES = Path(__file__).parents[1] / "fixtures"


@pytest.fixture(scope="session")
def completed_evidence(tmp_path_factory):
    root = tmp_path_factory.mktemp("context-evidence")
    receipts = []
    for name in ("call-yield", "call-yield", "matching"):
        data = (FIXTURES / (name + ".faultglass.json")).read_bytes()
        report, _path, code = run_case(data, read_case(data), "call-yield-c-rust", root)
        assert code == 0, (
            "Prepare Docker and both approved engine images using the investigator setup instructions."
        )
        receipts.append(report)
    return root, receipts


@pytest.fixture
def repository(completed_evidence):
    root, _ = completed_evidence
    repo = GraphRepository(
        ContextConfig(graph="faultglass__test_" + uuid4().hex, artifact_root=root)
    )
    try:
        repo.ensure_schema()
    except Exception as error:
        repo.close()
        pytest.fail(
            f"Start the context service with docker compose up -d context before selecting context tests ({type(error).__name__})."
        )
    try:
        yield repo
    finally:
        assert repo.config.graph.startswith("faultglass__test_")
        repo.graph.delete()
        repo.close()
