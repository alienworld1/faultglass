MATCH (n) WITH labels(n) AS labels,n.id AS id,count(n) AS copies
WHERE copies<>1 OR id IS NULL OR size(labels)<>1 RETURN labels,id,copies LIMIT 1
