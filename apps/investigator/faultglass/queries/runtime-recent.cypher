MATCH (i:Investigation)
WHERE i.runtime_version='runtime-v1' AND i.workspace_id='falkordb-core'
RETURN i.id ORDER BY i.updated_at DESC, i.id LIMIT 10
