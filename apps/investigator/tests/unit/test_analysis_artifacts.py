from uuid import uuid4

import pytest

from faultglass.analysis_artifacts import AnalysisStore
from faultglass.analysis_models import DownloadReference
from faultglass.context_artifacts import read_reference
from faultglass.context_errors import EvidenceIntegrity, IdentityConflict
from faultglass.context_models import EvidenceReference


def test_download_access_is_narrow_and_hash_verified(tmp_path):
    job = str(uuid4())
    (tmp_path / job).mkdir(mode=0o700)
    storage = AnalysisStore(tmp_path, job, "export")
    ref = storage.put("case_regression_test.py", b"print(1)\n", key="regression-test")
    assert read_reference(tmp_path, ref) == b"print(1)\n"
    with pytest.raises(ValueError):
        EvidenceReference.model_validate(ref.model_dump(exclude={"key"}))
    for update in [
        {"owner": job + "/runtime"},
        {"path": "../case.py"},
        {"mediaType": "text/html"},
        {"bytes": 262145},
    ]:
        with pytest.raises(ValueError):
            DownloadReference.model_validate({**ref.model_dump(), **update})
    with pytest.raises(IdentityConflict):
        storage.put(ref.path, b"print(2)\n", key="regression-test")
    (tmp_path / ref.owner / ref.path).write_bytes(b"corrupt")
    with pytest.raises(EvidenceIntegrity):
        read_reference(tmp_path, ref)
