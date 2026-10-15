MATCH (i:Investigation)-[:EXECUTED_AS]->(r:Run)-[:ON_VERSION]->(engine:EngineVersion)
MATCH (r)-[:PRODUCED]->(d:Divergence)-[classification:MATCHES_FAMILY]->(family:FaultFamily {id:$family_id})
WHERE i.workspace_id='falkordb-core' AND i.context_recorded_at IS NOT NULL AND i.id<>$exclude_id
AND classification.status IN ['provisional','confirmed'] AND classification.source_kind='verified_classification'
AND classification.version_scope=$scope
WITH DISTINCT i, classification ORDER BY i.id, classification.id
WITH i, head(collect(classification)) AS source
RETURN i.id, source.source_id, source.evidence_weight, source.id
ORDER BY i.id LIMIT 5
