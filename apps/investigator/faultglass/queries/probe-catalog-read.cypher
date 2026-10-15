MATCH (p:Probe) WHERE p.id IN $ids
OPTIONAL MATCH (p)-[e:TARGETS_FEATURE]->(f:Feature)
RETURN properties(p), properties(e), f.id ORDER BY p.id, f.id
