MATCH (i:Investigation {id:$id}) WHERE i.revision=$expected
FOREACH (props IN $FaultCase |
 MERGE (n:FaultCase {id:props.id}) ON CREATE SET n += props
)
FOREACH (props IN $Fingerprint |
 MERGE (n:Fingerprint {id:props.id}) ON CREATE SET n += props
)
FOREACH (props IN $EngineVersion |
 MERGE (n:EngineVersion {id:props.id}) ON CREATE SET n += props
)
FOREACH (props IN $Run |
 MERGE (n:Run {id:props.id}) ON CREATE SET n += props
)
FOREACH (props IN $Divergence |
 MERGE (n:Divergence {id:props.id}) ON CREATE SET n += props
)
FOREACH (entry IN $STARTED_FROM |
 MERGE (a:Investigation {id:entry.source_id})
 MERGE (b:FaultCase {id:entry.target_id})
 MERGE (a)-[r:STARTED_FROM {id:entry.properties.id}]->(b) ON CREATE SET r += entry.properties
)
FOREACH (entry IN $HAS_FINGERPRINT |
 MERGE (a:FaultCase {id:entry.source_id})
 MERGE (b:Fingerprint {id:entry.target_id})
 MERGE (a)-[r:HAS_FINGERPRINT {id:entry.properties.id}]->(b) ON CREATE SET r += entry.properties
)
FOREACH (entry IN $USES_FEATURE |
 MERGE (a:Fingerprint {id:entry.source_id})
 MERGE (b:Feature {id:entry.target_id})
 MERGE (a)-[r:USES_FEATURE {id:entry.properties.id}]->(b) ON CREATE SET r += entry.properties
)
FOREACH (entry IN $SELECTED_PROBE |
 MERGE (a:Investigation {id:entry.source_id})
 MERGE (b:Probe {id:entry.target_id})
 MERGE (a)-[r:SELECTED_PROBE {id:entry.properties.id}]->(b) ON CREATE SET r += entry.properties
)
FOREACH (entry IN $EXECUTED_AS |
 MERGE (a:Investigation {id:entry.source_id})
 MERGE (b:Run {id:entry.target_id})
 MERGE (a)-[r:EXECUTED_AS {id:entry.properties.id}]->(b) ON CREATE SET r += entry.properties
)
FOREACH (entry IN $ON_VERSION |
 MERGE (a:Run {id:entry.source_id})
 MERGE (b:EngineVersion {id:entry.target_id})
 MERGE (a)-[r:ON_VERSION {id:entry.properties.id}]->(b) ON CREATE SET r += entry.properties
)
FOREACH (entry IN $PRODUCED |
 MERGE (a:Run {id:entry.source_id})
 MERGE (b:Divergence {id:entry.target_id})
 MERGE (a)-[r:PRODUCED {id:entry.properties.id}]->(b) ON CREATE SET r += entry.properties
)
FOREACH (entry IN $REDUCED_TO |
 MERGE (a:Divergence {id:entry.source_id})
 MERGE (b:FaultCase {id:entry.target_id})
 MERGE (a)-[r:REDUCED_TO {id:entry.properties.id}]->(b) ON CREATE SET r += entry.properties
)
SET i += $props
RETURN i.id, i.revision
