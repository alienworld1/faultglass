UNWIND $probes AS entry
MERGE (p:Probe {id:entry.node.id}) ON CREATE SET p += entry.node
WITH p, entry
UNWIND entry.targets AS target
MATCH (f:Feature {id:target.target_id})
MERGE (p)-[e:TARGETS_FEATURE {id:target.properties.id}]->(f) ON CREATE SET e += target.properties
RETURN p.id
