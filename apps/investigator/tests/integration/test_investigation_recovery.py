import os
import subprocess
import sys
import textwrap
from pathlib import Path
from uuid import uuid4

import pytest

from faultglass.context_config import ContextConfig
from faultglass.graph_repository import GraphRepository
from faultglass.investigation_models import Admission, Status
from faultglass.investigation_store import InvestigationStore
from faultglass.worker import Worker

pytestmark = [pytest.mark.docker, pytest.mark.context]


@pytest.mark.parametrize("complete", [True, False])
def test_worker_process_reconciles_reserved_child_without_reexecution(
    tmp_path, complete
):
    repo = GraphRepository(
        ContextConfig(graph="faultglass__test_" + uuid4().hex, artifact_root=tmp_path)
    )
    repo.ensure_schema()
    store = InvestigationStore(repo)
    source = (
        Path(__file__).parents[1] / "fixtures/call-yield.faultglass.json"
    ).read_text()
    record, _ = store.admit(
        Admission(caseFile=source, pairId="call-yield-c-rust"), str(uuid4())
    )
    worker = Worker(repo)
    try:
        for _ in range(4):
            worker.step(record.snapshot.id)
        reserved = store.load(record.snapshot.id)
        assert reserved.snapshot.status == Status.PROBING
        child = reserved.reservation.childId
        environment = {
            **os.environ,
            "FAULTGLASS_CONTEXT_GRAPH": repo.config.graph,
            "FAULTGLASS_ARTIFACT_ROOT": str(tmp_path),
            "RECOVERY_JOB": record.snapshot.id,
        }
        # The subprocess exits at an injected test barrier, never a production switch.
        if complete:
            barrier = """
            worker.complete_execution = lambda record: os._exit(77)
            """
        else:
            barrier = """
            module.run_case = lambda *args, **kwargs: os._exit(77)
            """
        script = (
            """
import os
import faultglass.worker as module
from faultglass.graph_repository import GraphRepository
worker = module.Worker(GraphRepository())
"""
            + textwrap.dedent(barrier)
            + '\nworker.step(os.environ["RECOVERY_JOB"])\n'
        )
        process = subprocess.run(
            [sys.executable, "-c", script],
            env=environment,
            capture_output=True,
            timeout=90,
        )
        assert process.returncode == 77, process.stderr.decode()
        persisted = store.load(record.snapshot.id)
        assert persisted.reservation.childId == child
        manifest = tmp_path / child / "manifest.json"
        before = manifest.read_bytes() if complete else None
        restart = """
import os
import faultglass.worker as module
from faultglass.graph_repository import GraphRepository
module.run_case = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('Execution repeated during recovery'))
worker = module.Worker(GraphRepository())
worker.cleanup()
worker.step(os.environ['RECOVERY_JOB'])
"""
        process = subprocess.run(
            [sys.executable, "-c", restart],
            env=environment,
            capture_output=True,
            timeout=30,
        )
        assert process.returncode == 0, process.stderr.decode()
        final = store.load(record.snapshot.id)
        if complete:
            assert final.snapshot.status == Status.PLANNING
            assert manifest.read_bytes() == before
            assert final.snapshot.budget.reservedProbes == 1
        else:
            assert final.snapshot.status == Status.FAILED
            assert final.snapshot.terminalReason.code == "recovery_required"
            assert not manifest.exists()
    finally:
        repo.graph.delete()
        repo.close()
