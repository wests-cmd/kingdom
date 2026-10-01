import pytest
import time
from uuid import uuid4
from backend.cluster.identity import KingdomIdentity, KnightIdentity
from backend.cluster.mobile_pairing import mobile_pairing_manager, MobileDeviceState
from backend.memory.ingestion import knowledge_ingestor
from backend.memory.knowledge_domains import knowledge_domain_manager
from backend.skills.learning_engine import skill_learning_engine
from backend.integrations.financial import financial_engine
from backend.security.approval_engine import approval_engine

def test_mobile_pairing_and_revocation_lifecycle():
    k_identity = KingdomIdentity.get_or_create()
    ch = mobile_pairing_manager.create_pairing_challenge(ttl_seconds=300)
    code = ch["code"]

    # Generate mobile device keys
    kn_device = KnightIdentity("mbl-iphone-" + uuid4().hex, "John iPhone")
    msg = f"{code}:{kn_device.node_id}:{k_identity.node_id}".encode("utf-8")
    sig = kn_device.sign_message(msg).hex()

    req = {
        "code": code,
        "device_id": kn_device.node_id,
        "device_name": "John iPhone",
        "device_public_key_hex": kn_device.get_public_identity()["public_key_hex"],
        "signature": sig
    }

    # Pair device
    res = mobile_pairing_manager.process_mobile_pairing(req)
    assert res["success"] is True
    assert res["device_state"] == MobileDeviceState.PENDING.value

    # Approve device
    assert mobile_pairing_manager.approve_mobile_device(kn_device.node_id) is True

    # Revoke device
    assert mobile_pairing_manager.revoke_mobile_device(kn_device.node_id, reason="Security test") is True

def test_universal_knowledge_ingestion_and_source_of_truth_conflict():
    unique_domain = f"Pricing-Test-{int(time.time() * 1000)}"
    # Ingest document
    doc_text = "Official Pricing Sheet: Standard labor rate is $85/hr for standard repair."
    extracted = knowledge_ingestor.process_file_or_text(doc_text, filename="pricing_v1.txt")
    assert extracted["intent"]["domain"] == "Invoices"
    assert len(extracted["extracted_entities"]) > 0

    # Add knowledge as source of truth
    res1 = knowledge_domain_manager.add_knowledge_item({
        "content": doc_text,
        "domain": unique_domain,
        "is_source_of_truth": True
    })
    assert res1["conflicts_detected"] is False

    # Add conflicting newer document as source of truth
    doc_text_v2 = "Official Pricing Sheet V2: Standard labor rate is $95/hr for standard repair."
    res2 = knowledge_domain_manager.add_knowledge_item({
        "content": doc_text_v2,
        "domain": unique_domain,
        "is_source_of_truth": True
    })
    assert res2["conflicts_detected"] is True
    assert len(res2["conflicts"]) > 0

def test_skill_learning_and_promotion_pipeline():
    # Learn skill from demonstration
    res_learn = skill_learning_engine.learn_skill_from_examples(
        skill_name="Auto Repair Invoice",
        description="Extracts automotive repair line items and calculates tax",
        example_texts=["Customer John: Alternator replacement $180, Labor 3 hours at $85/hr."]
    )
    assert res_learn["success"] is True
    assert res_learn["status"] == "DRAFT"
    skill_id = res_learn["skill"]["id"]

    # Promote skill to ACTIVE
    res_promo = skill_learning_engine.test_and_promote_skill(skill_id, governance_approved=True)
    assert res_promo["success"] is True
    assert res_promo["status"] == "ACTIVE"

def test_financial_feature_never_fabricates_accounts_market_data_or_trades():
    research = financial_engine.research_market_and_dividends("SCHD dividends")
    assert research["success"] is False
    assert research["candidates"] == []
    connection = financial_engine.connect_broker_account("Interactive Brokers", "test-token")
    assert connection["success"] is False
    assert financial_engine.connected_broker is None
    assert financial_engine.draft_order_preview("SCHD", "buy", 10, 78.50)["success"] is False
    assert financial_engine.execute_approved_order("invented-approval")["success"] is False
