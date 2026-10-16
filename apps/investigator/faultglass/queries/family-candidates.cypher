MATCH (fp:Fingerprint {id:$fingerprint})-[:USES_FEATURE]->(feature:Feature)<-[involves:INVOLVES_FEATURE]-(family:FaultFamily)
MATCH (d:Divergence)-[classification:MATCHES_FAMILY]->(family)
WHERE family.status IN ['provisional','confirmed'] AND family.superseded_by_id IS NULL
AND classification.source_kind='verified_classification' AND d.investigation_id<>$exclude_id
WITH family, classification, collect(DISTINCT involves.id) AS paths
RETURN properties(family), properties(classification), paths ORDER BY family.id, classification.id LIMIT 101
