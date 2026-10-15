MATCH (i:Investigation {id:$id})-[e:SELECTED_PROBE]->(p:Probe)
WHERE e.sequence=1
RETURN type(e) AS kind, i.id AS source, p.id AS target, properties(e) AS props
UNION
MATCH (i:Investigation {id:$id})-[e:EXECUTED_AS {sequence:1}]->(r:Run)
RETURN type(e) AS kind, i.id AS source, r.id AS target, properties(e) AS props
UNION
MATCH (i:Investigation {id:$id})-[:EXECUTED_AS {sequence:1}]->(r:Run)-[e:ON_VERSION]->(v:EngineVersion)
RETURN type(e) AS kind, r.id AS source, v.id AS target, properties(e) AS props
UNION
MATCH (i:Investigation {id:$id})-[:EXECUTED_AS {sequence:1}]->(r:Run)-[e:PRODUCED]->(d:Divergence)
RETURN type(e) AS kind, r.id AS source, d.id AS target, properties(e) AS props
