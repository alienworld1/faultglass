MATCH (i:Investigation {admission_key:$key}) RETURN i.id LIMIT 2
