MATCH ()-[e]->() WITH e.id AS id,count(e) AS copies
WHERE id IS NULL OR copies<>1 RETURN id,copies LIMIT 1
