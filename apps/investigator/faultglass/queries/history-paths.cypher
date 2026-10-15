MATCH (fp:Fingerprint {id:$fingerprint})-[e:USES_FEATURE]->(f:Feature)
RETURN type(e) AS kind, fp.id AS source, f.id AS target, properties(e) AS props
UNION
MATCH (family:FaultFamily {id:$family})-[e:INVOLVES_FEATURE]->(f:Feature)
RETURN type(e) AS kind, family.id AS source, f.id AS target, properties(e) AS props
UNION
MATCH (probe:Probe {id:$probe})-[e:TARGETS_FEATURE]->(f:Feature)
RETURN type(e) AS kind, probe.id AS source, f.id AS target, properties(e) AS props
UNION
MATCH (d:Divergence)-[e:MATCHES_FAMILY]->(family:FaultFamily {id:$family}) WHERE e.id IN $classifications
RETURN type(e) AS kind, d.id AS source, family.id AS target, properties(e) AS props
