MATCH (n:Feature) WHERE NOT n.id IN $ids RETURN n.id LIMIT 1
