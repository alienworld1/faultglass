CATALOG_VERSION = "features-v1"

DESCRIPTIONS = {
    "CALL": "A procedure call is present.",
    "YIELD": "Procedure outputs are introduced.",
    "MATCH": "A required graph pattern is matched.",
    "OPTIONAL_MATCH": "An optional graph pattern is matched.",
    "WITH": "A pipeline projection is present.",
    "WHERE": "A predicate filters the query.",
    "UNWIND": "A list is expanded into rows.",
    "CREATE": "A graph creation clause is present.",
    "MERGE": "A graph merge clause is present.",
    "RETURN": "A result projection is present.",
    "WRITE_CLAUSE": "A graph write clause is present.",
    "PROPERTY_ACCESS": "A property is accessed on an expression.",
    "DISTINCT": "Duplicate elimination is requested.",
    "ORDERING": "An explicit ordering clause is present.",
    "LIMIT": "A result limit is present.",
    "SKIP": "A result offset is present.",
    "AGGREGATION": "A recognized aggregation function is called.",
    "NULL_SEMANTICS": "A null literal or null-sensitive operator is present.",
    "UNION": "Query branches are combined.",
    "SUBQUERY": "A nested query scope is present.",
    "VARIABLE_LENGTH_PATH": "A relationship has a variable length.",
    "PATH_VALUE": "A matched path is assigned to a variable.",
    "ALIAS_SCOPE": "A variable binding or explicit alias is introduced.",
    "RELATIONSHIP_TYPE_CARDINALITY": "A relationship pattern has multiple type alternatives.",
}
CATALOG = [
    {
        "id": key,
        "label": key.replace("_", " ").title(),
        "description": description,
        "catalog_version": CATALOG_VERSION,
    }
    for key, description in sorted(DESCRIPTIONS.items())
]
FEATURE_IDS = tuple(entry["id"] for entry in CATALOG)
