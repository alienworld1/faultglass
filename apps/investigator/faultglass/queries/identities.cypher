MATCH (n) WHERE n.id IN $ids RETURN labels(n), properties(n) LIMIT 128
