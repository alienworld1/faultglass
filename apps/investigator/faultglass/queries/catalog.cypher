UNWIND $features AS props MERGE (n:Feature {id:props.id}) ON CREATE SET n += props RETURN n.id
