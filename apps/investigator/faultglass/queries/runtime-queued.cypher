MATCH (i:Investigation {status:'QUEUED'}) WHERE i.runtime_version='runtime-v1' RETURN count(i)
