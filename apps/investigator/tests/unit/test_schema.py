from pathlib import Path

from faultglass.jsonio import loads
from faultglass.schema import export_schema


def test_frontend_schema_is_the_exported_authoritative_contract():
    schema = Path(__file__).parents[3] / "web/src/contracts/evidence.schema.json"
    assert loads(schema.read_bytes()) == export_schema()
