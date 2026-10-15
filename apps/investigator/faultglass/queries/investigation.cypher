MATCH (i:Investigation {id:$id})-[:STARTED_FROM]->(c:FaultCase)-[:HAS_FINGERPRINT {fingerprint_version:$version}]->(fp:Fingerprint)
WHERE i.context_recorded_at IS NOT NULL
OPTIONAL MATCH (fp)-[:USES_FEATURE]->(f:Feature)
WITH i,c,fp,collect(DISTINCT f.id) AS features
MATCH (i)-[execution:EXECUTED_AS {sequence:0}]->(r:Run)-[:ON_VERSION]->(e:EngineVersion)
WHERE execution.purpose IS NULL
OPTIONAL MATCH (r)-[:PRODUCED]->(d:Divergence)
RETURN properties(i), properties(c), properties(fp), features, properties(r), properties(e), properties(d)
ORDER BY r.role LIMIT 4
