MATCH (n) OPTIONAL MATCH (n)-[e]->() RETURN count(DISTINCT n), count(e)
