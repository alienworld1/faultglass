MATCH (fp:Fingerprint {id:$id})-[:USES_FEATURE]->(f:Feature)<-[:INVOLVES_FEATURE]-(family:FaultFamily)<-[eff:EFFECTIVE_FOR]-(probe:Probe)
WHERE family.status IN ['provisional','confirmed'] AND probe.enabled=true
WITH family, probe, eff, collect(DISTINCT f.id) AS features
MATCH (i:Investigation)-[:EXECUTED_AS]->(r:Run)-[:PRODUCED]->(d:Divergence)-[classification:MATCHES_FAMILY]->(family)
WHERE i.workspace_id='falkordb-core' AND i.context_recorded_at IS NOT NULL AND i.id<>$exclude_id
AND classification.status IN ['provisional','confirmed'] AND classification.source_kind='verified_classification'
AND classification.version_scope=eff.version_scope
WITH family,probe,eff,features,count(DISTINCT i.id) AS sources
WHERE sources>0
RETURN properties(family), properties(probe), properties(eff), features
ORDER BY size(features) DESC, family.id, probe.id, eff.version_scope LIMIT $limit
