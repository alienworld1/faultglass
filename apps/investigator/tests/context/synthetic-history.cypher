MATCH (i:Investigation {id:$investigation_id})-[:EXECUTED_AS]->(:Run)-[:PRODUCED]->(d:Divergence)
WITH DISTINCT i,d
MATCH (a:Feature {id:'CALL'}), (b:Feature {id:'YIELD'})
CREATE (family:FaultFamily {id:$family_id,created_at:$now,updated_at:$now,slug:'synthetic-call',name:'Synthetic call evidence',status:'confirmed'})
CREATE (probe:Probe {id:$probe_id,created_at:$now,type:'SYNTHETIC_PROJECTION',template_version:'fixture-v1',description:'Explicit synthetic history for traversal verification.',cost_class:'small',enabled:true})
CREATE (probe)-[:TARGETS_FEATURE {id:$target_edge,created_at:$now,source_kind:'catalog',source_id:'synthetic-history-v1'}]->(a)
CREATE (family)-[:INVOLVES_FEATURE {id:$feature_a_edge,created_at:$now,source_kind:'verified_classification',source_id:$reference}]->(a)
CREATE (family)-[:INVOLVES_FEATURE {id:$feature_b_edge,created_at:$now,source_kind:'verified_classification',source_id:$reference}]->(b)
CREATE (probe)-[:EFFECTIVE_FOR {id:$effective_edge,created_at:$now,source_kind:'verified_classification',source_id:$reference,attempts:4,successes:3,avg_cost_ms:20.0,last_seen_at:$now,version_scope:$scope}]->(family)
CREATE (d)-[:MATCHES_FAMILY {id:$classification_edge,created_at:$now,source_kind:'verified_classification',source_id:$reference,status:'confirmed',evidence_weight:1.0,version_scope:$scope}]->(family)
RETURN family.id
