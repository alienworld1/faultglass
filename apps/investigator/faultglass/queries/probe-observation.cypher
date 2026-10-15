MATCH (i:Investigation {id:$investigation_id}), (be:EngineVersion {id:$baseline_engine_id}), (te:EngineVersion {id:$target_engine_id})
MERGE (b:Run {id:$baseline_run.id}) ON CREATE SET b += $baseline_run
MERGE (t:Run {id:$target_run.id}) ON CREATE SET t += $target_run
MERGE (i)-[eb:EXECUTED_AS {id:$executed_baseline.id}]->(b) ON CREATE SET eb += $executed_baseline
MERGE (i)-[et:EXECUTED_AS {id:$executed_target.id}]->(t) ON CREATE SET et += $executed_target
MERGE (b)-[ob:ON_VERSION {id:$on_baseline.id}]->(be) ON CREATE SET ob += $on_baseline
MERGE (t)-[ot:ON_VERSION {id:$on_target.id}]->(te) ON CREATE SET ot += $on_target
FOREACH (props IN $divergences |
 MERGE (d:Divergence {id:props.id}) ON CREATE SET d += props
 MERGE (b)-[pb:PRODUCED {id:$produced_baseline.id}]->(d) ON CREATE SET pb += $produced_baseline
 MERGE (t)-[pt:PRODUCED {id:$produced_target.id}]->(d) ON CREATE SET pt += $produced_target
)
SET i.observation_phase_key=$phase_key, i.observation_payload_sha256=$payload_sha256,
 i.observation_committed_at=$committed_at, i.observation_artifact_ref=$artifact_ref
RETURN i.id
