MATCH (a)-[e]->(b) WHERE e.id IN $ids RETURN type(e), a.id, b.id, properties(e) LIMIT 128
