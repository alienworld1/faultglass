MATCH (i:Investigation) WHERE i.runtime_version='runtime-v1' AND NOT i.status IN $terminal
RETURN i.id ORDER BY i.created_at, i.id LIMIT 9
