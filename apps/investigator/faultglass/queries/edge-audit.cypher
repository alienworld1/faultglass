MATCH (a)-[e]->(b) RETURN DISTINCT type(e), labels(a), labels(b) LIMIT 32
