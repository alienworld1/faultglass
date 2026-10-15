import os
from uuid import uuid4

import pytest

from faultglass.artifacts import open_private_root
from faultglass.context_artifacts import read_reference
from faultglass.context_errors import EvidenceIntegrity, IdentityConflict
from faultglass.jsonio import encode
from faultglass.planner_models import ExecutionJournal
from faultglass.planning_artifacts import PlanningStore

NOW = "2026-10-15T00:00:00+00:00"


def store_at(root):
    seed = str(uuid4())
    _, fd = open_private_root(root / seed)
    os.close(fd)
    return PlanningStore(root, seed)


def test_sealed_files_replay_privately_and_reject_edits_links_and_traversal(tmp_path):
    store = store_at(tmp_path)
    documents = {"plan.json": encode({"saved": True}), "source-snapshot.json": b"{}"}
    refs = store.seal("selection", documents)
    assert store.verify("selection") == refs
    assert store.seal("selection", documents) == refs
    for ref in refs:
        assert (tmp_path / ref.owner / ref.path).stat().st_mode & 0o777 == 0o600
    with pytest.raises(IdentityConflict):
        store.put("plan.json", b"{}")
    with pytest.raises(EvidenceIntegrity):
        store.put("../bad.json", b"{}")
    path = tmp_path / refs[0].owner / refs[0].path
    path.unlink()
    path.symlink_to("/etc/passwd")
    with pytest.raises(EvidenceIntegrity):
        read_reference(tmp_path, refs[0])


def test_document_and_total_caps_and_journal_ownership(tmp_path):
    store = store_at(tmp_path)
    with pytest.raises(EvidenceIntegrity):
        store.put("oversized.json", b"x" * 1048577)
    for index in range(4):
        store.put(str(index) + ".json", b"x" * 1048576)
    with pytest.raises(EvidenceIntegrity):
        store.put("overflow.json", b"{}")
    store = store_at(tmp_path)
    journal = ExecutionJournal(
        selection_id="a" * 64,
        child_evidence_id=str(uuid4()),
        state="reserved",
        reserved_at=NOW,
    )
    store.advance(journal)
    assert store.journal() == journal
    with pytest.raises(IdentityConflict):
        store.advance(journal.model_copy(update={"child_evidence_id": str(uuid4())}))
    started = journal.model_copy(update={"state": "started", "started_at": NOW})
    store.advance(started)
    with pytest.raises(IdentityConflict):
        store.advance(journal)
