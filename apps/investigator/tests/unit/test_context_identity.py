from faultglass.canonicalize import case_identity, statement_tokens
from faultglass.fingerprint import extract_fingerprint
from faultglass.models import FaultCase


def case(query="MATCH (n) RETURN n", **changes):
    return FaultCase.model_validate(
        {
            "schemaVersion": 1,
            "title": "A case",
            "setup": [],
            "query": query,
            "observation": {"compareResult": True, "ordering": "unordered"},
            **changes,
        }
    )


def test_case_identity_ignores_presentation_and_lexical_spacing():
    first = case("MATCH (n) RETURN n;")
    second = case(
        "/* note */ MATCH\n(n) RETURN n",
        title="Another title",
        metadata={"notes": "Edited"},
    )
    assert case_identity(first) == case_identity(second)
    assert statement_tokens("RETURN a b") != statement_tokens("RETURN ab")


def test_case_identity_preserves_material_content_and_defaults():
    baseline = case_identity(case())[0]
    for changed in [
        case("MATCH (m) RETURN m"),
        case(parameters={"x": 1}),
        case(setup=["CREATE ()"]),
        case(expectation={"kind": "none"}),
        case(observation={"compareResult": False, "ordering": "ordered"}),
    ]:
        assert case_identity(changed)[0] != baseline
    assert case_identity(case(parameters={})) == case_identity(case())
    assert case_identity(case("RETURN '/* text */'")) != case_identity(
        case("RETURN ''")
    )


def fingerprint(query):
    return extract_fingerprint(case(query))


def test_supported_variable_and_scalar_return_convergence():
    assert (
        fingerprint("MATCH (n:Person) RETURN n.name")["id"]
        == fingerprint("match (x:Person) return x.name")["id"]
    )
    assert fingerprint("RETURN 1, 2, 1")["id"] == fingerprint("RETURN 8, 9, 8")["id"]
    assert fingerprint("RETURN 'a'")["id"] == fingerprint("RETURN 'b'")["id"]


def test_structurally_meaningful_differences_remain_distinct():
    pairs = [
        ("RETURN 1, 1", "RETURN 1, 2"),
        ("RETURN 0", "RETURN 1"),
        ("RETURN null", "RETURN true"),
        ("RETURN 1", "RETURN 1.5"),
        ("MATCH (n:A) RETURN n.x", "MATCH (n:B) RETURN n.x"),
        ("MATCH (n) RETURN n.x", "MATCH (n) RETURN n.y"),
        ("MATCH (n)-[:A*1..2]->(m) RETURN n", "MATCH (n)-[:A*1..3]->(m) RETURN n"),
        ("MATCH (n)-[:A|B]->(m) RETURN n", "MATCH (n)-[:A]->(m) RETURN n"),
        ("MATCH (n) WITH n RETURN n", "MATCH (x) WITH x RETURN x"),
        ("MATCH (n) RETURN n AS x", "MATCH (n) RETURN n AS y"),
        ("RETURN $a", "RETURN $b"),
        ("RETURN [1,2]", "RETURN [2,1]"),
        ("RETURN 1 LIMIT 2", "RETURN 1 LIMIT 3"),
    ]
    for a, b in pairs:
        assert fingerprint(a)["id"] != fingerprint(b)["id"], (a, b)


def test_catalog_detectors_ignore_quoted_content_and_identifier_roles():
    features = fingerprint(
        "OPTIONAL MATCH (n) WHERE n.x IS NULL RETURN DISTINCT count(n) ORDER BY n.x SKIP 1 LIMIT 2"
    )["feature_ids"]
    assert set(features) == {
        "OPTIONAL_MATCH",
        "WHERE",
        "NULL_SEMANTICS",
        "RETURN",
        "DISTINCT",
        "AGGREGATION",
        "ORDERING",
        "SKIP",
        "LIMIT",
        "PROPERTY_ACCESS",
        "ALIAS_SCOPE",
    }
    assert fingerprint("RETURN 'MATCH CALL', `YIELD` /* CREATE */")["feature_ids"] == [
        "RETURN"
    ]
    assert "MATCH" not in fingerprint("RETURN n.MATCH")["feature_ids"]
    assert {"CALL", "YIELD", "MATCH"} <= set(
        fingerprint("CALL db.labels() YIELD label MATCH (n)")["feature_ids"]
    )
    assert {
        "PATH_VALUE",
        "RELATIONSHIP_TYPE_CARDINALITY",
        "VARIABLE_LENGTH_PATH",
    } <= set(fingerprint("MATCH p=(n)-[:A|B*1..3]->(m) RETURN p")["feature_ids"])
    assert "WRITE_CLAUSE" in fingerprint("CREATE (n) RETURN n")["feature_ids"]
    assert "SUBQUERY" in fingerprint("CALL { RETURN 1 } RETURN 1")["feature_ids"]
    assert (
        fingerprint("CALL { RETURN 1 } RETURN 1")["analysis_support"] == "conservative"
    )


def test_uncertain_bindings_and_nonbindings_do_not_alpha_converge():
    for a, b in [
        ("RETURN (n)", "RETURN (x)"),
        ("MATCH (n) RETURN [n IN [1,2] | n]", "MATCH (x) RETURN [x IN [1,2] | x]"),
        (
            "MATCH (n) RETURN all(n IN [1] WHERE n>0)",
            "MATCH (x) RETURN all(x IN [1] WHERE x>0)",
        ),
        (
            "CALL { MATCH (n) RETURN n } RETURN n",
            "CALL { MATCH (x) RETURN x } RETURN x",
        ),
    ]:
        assert fingerprint(a)["id"] != fingerprint(b)["id"]
    assert fingerprint("RETURN {MATCH: 'YIELD'}")["feature_ids"] == ["RETURN"]


def test_every_emitted_catalog_feature_has_a_syntactic_detector():
    examples = {
        "CALL": "CALL db.labels()",
        "YIELD": "CALL db.labels() YIELD label",
        "MATCH": "MATCH (n) RETURN n",
        "OPTIONAL_MATCH": "OPTIONAL MATCH (n) RETURN n",
        "WITH": "WITH 1 AS x RETURN x",
        "WHERE": "MATCH (n) WHERE n.x=1 RETURN n",
        "UNWIND": "UNWIND [1,2] AS x RETURN x",
        "CREATE": "CREATE ()",
        "MERGE": "MERGE ()",
        "RETURN": "RETURN 1",
        "WRITE_CLAUSE": "MATCH (n) DELETE n",
        "PROPERTY_ACCESS": "MATCH (n) RETURN n.x",
        "DISTINCT": "RETURN DISTINCT 1",
        "ORDERING": "RETURN 1 ORDER BY 1",
        "LIMIT": "RETURN 1 LIMIT 1",
        "SKIP": "RETURN 1 SKIP 1",
        "AGGREGATION": "RETURN sum(1)",
        "NULL_SEMANTICS": "RETURN null",
        "UNION": "RETURN 1 UNION RETURN 2",
        "SUBQUERY": "CALL { RETURN 1 } RETURN 1",
        "VARIABLE_LENGTH_PATH": "MATCH ()-[:R*1..2]->() RETURN 1",
        "PATH_VALUE": "MATCH p=()-[:R]->() RETURN p",
        "ALIAS_SCOPE": "RETURN 1 AS x",
        "RELATIONSHIP_TYPE_CARDINALITY": "MATCH ()-[:A|B]->() RETURN 1",
    }
    from faultglass.feature_catalog import FEATURE_IDS

    assert set(examples) == set(FEATURE_IDS)
    for feature, query in examples.items():
        assert feature in fingerprint(query)["feature_ids"], feature
