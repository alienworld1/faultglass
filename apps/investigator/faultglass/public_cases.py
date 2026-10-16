from .jsonio import encode
from .models import read_case

FLAGSHIP = {
    "schemaVersion": 1,
    "title": "Trailing MATCH after a procedure call",
    "setup": ["CREATE (:N)"],
    "query": "CALL db.labels() YIELD label MATCH (n)",
    "observation": {"compareResult": True, "ordering": "unordered"},
    "metadata": {"source": "https://github.com/FalkorDB/FalkorDB/issues/3279"},
}
RELATED = {
    **FLAGSHIP,
    "title": "Trailing MATCH with two node labels",
    "setup": ["CREATE (:N), (:Other)"],
    "query": "CALL db.labels() YIELD label MATCH (other)",
}
PUBLIC_CASES = [read_case(encode(value)) for value in (FLAGSHIP, RELATED)]


def is_public(case):
    return any(case == approved for approved in PUBLIC_CASES)
