MATCH (i:Investigation {id:$investigation_id})
OPTIONAL MATCH (p:Probe {id:$probe_id})
FOREACH (entry IN $selections |
 MERGE (i)-[s:SELECTED_PROBE {id:entry.properties.id}]->(p)
 ON CREATE SET s += entry.properties
)
SET i.selection_phase_key=$phase_key, i.selection_payload_sha256=$payload_sha256,
 i.selection_committed_at=$committed_at, i.selection_artifact_ref=$artifact_ref
RETURN i.id
