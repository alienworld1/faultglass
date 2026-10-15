MATCH (i:Investigation) RETURN DISTINCT i.context_schema_version, i.canonicalization_version, i.fingerprint_version LIMIT 8
