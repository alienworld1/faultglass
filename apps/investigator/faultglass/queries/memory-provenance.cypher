MATCH (i:Investigation)-[:EXECUTED_AS]->(r:Run)-[:PRODUCED]->(d:Divergence)-[classification:MATCHES_FAMILY]->(family:FaultFamily {id:$family_id})
WHERE i.id IN $ids AND classification.source_kind='verified_classification' AND classification.version_scope=$scope
RETURN DISTINCT i.id, classification.source_id, classification.evidence_weight, classification.id ORDER BY i.id
