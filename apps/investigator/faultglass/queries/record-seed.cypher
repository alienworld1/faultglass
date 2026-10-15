MATCH (feature:Feature) WHERE feature.id IN $feature_ids
WITH collect(feature) AS features
MERGE (i:Investigation {id:$investigation.id})
ON CREATE SET i += $investigation
MERGE (c:FaultCase {id:$case_node.id})
ON CREATE SET c += $case_node
MERGE (fp:Fingerprint {id:$fingerprint.id})
ON CREATE SET fp += $fingerprint
MERGE (b:Run {id:$baseline_run.id})
ON CREATE SET b += $baseline_run
MERGE (t:Run {id:$target_run.id})
ON CREATE SET t += $target_run
MERGE (be:EngineVersion {id:$baseline_engine.id})
ON CREATE SET be += $baseline_engine
MERGE (te:EngineVersion {id:$target_engine.id})
ON CREATE SET te += $target_engine
MERGE (i)-[sc:STARTED_FROM {id:$started_from.id}]->(c)
ON CREATE SET sc += $started_from
MERGE (c)-[hf:HAS_FINGERPRINT {id:$has_fingerprint.id}]->(fp)
ON CREATE SET hf += $has_fingerprint
MERGE (i)-[eb:EXECUTED_AS {id:$executed_baseline.id}]->(b)
ON CREATE SET eb += $executed_baseline
MERGE (i)-[et:EXECUTED_AS {id:$executed_target.id}]->(t)
ON CREATE SET et += $executed_target
MERGE (b)-[ob:ON_VERSION {id:$on_baseline.id}]->(be)
ON CREATE SET ob += $on_baseline
MERGE (t)-[ot:ON_VERSION {id:$on_target.id}]->(te)
ON CREATE SET ot += $on_target
FOREACH (f IN features |
 MERGE (fp)-[uf:USES_FEATURE {id:head([row IN $uses_features WHERE row.target_id=f.id | row.properties.id])}]->(f)
 ON CREATE SET uf += head([row IN $uses_features WHERE row.target_id=f.id | row.properties])
)
FOREACH (props IN $divergences |
 MERGE (d:Divergence {id:props.id}) ON CREATE SET d += props
 MERGE (b)-[pb:PRODUCED {id:$produced_baseline.id}]->(d) ON CREATE SET pb += $produced_baseline
 MERGE (t)-[pt:PRODUCED {id:$produced_target.id}]->(d) ON CREATE SET pt += $produced_target
)
SET i.context_payload_sha256=$payload_sha256, i.context_recorded_at=$recorded_at
RETURN i.id, i.context_phase_key, i.context_payload_sha256
