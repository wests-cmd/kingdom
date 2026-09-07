import re
import json
import base64
from typing import Dict, Any, List, Optional
from backend.security.prompt_firewall import PromptFirewall
from backend.events.event_bus import event_bus

class UniversalKnowledgeIngestor:
    def __init__(self):
        self.firewall = PromptFirewall()

    def process_file_or_text(
        self,
        raw_content: bytes | str,
        filename: str = "input.txt",
        mime_type: str = "text/plain",
        source: str = "user_upload",
        owner: str = "user"
    ) -> Dict[str, Any]:
        # Convert bytes to text where applicable
        if isinstance(raw_content, bytes):
            try:
                text_content = raw_content.decode("utf-8", errors="ignore")
            except Exception:
                text_content = f"[Binary/OCR payload for {filename}]"
        else:
            text_content = raw_content

        # Zero-Trust Prompt Injection Defense on Document Content
        try:
            self.firewall.inspect(text_content[:2000])
            sanitized_text = text_content
            injection_detected = False
        except Exception as exc:
            sanitized_text = re.sub(r"(?i)(ignore previous instructions|send credentials|bypass security)", "[REDACTED UNTRUSTED PROMPT]", text_content)
            injection_detected = True
            event_bus.publish("security.document_injection_blocked", {"filename": filename, "reason": str(exc)}, source="knowledge_ingestion")

        # Intent Classification (Memory vs Source of Truth vs Skill Rule)
        intent = self._classify_intent(sanitized_text, filename)
        entities = self._extract_entities(sanitized_text)

        extracted = {
            "filename": filename,
            "mime_type": mime_type,
            "raw_snippet": sanitized_text[:500],
            "full_text": sanitized_text,
            "intent": intent,
            "extracted_entities": entities,
            "injection_detected": injection_detected,
            "owner": owner,
            "source": source
        }

        event_bus.publish("knowledge.processed", {
            "filename": filename,
            "intent": intent["primary_intent"]
        }, source="knowledge_ingestion")

        return extracted

    def _classify_intent(self, text: str, filename: str) -> Dict[str, Any]:
        text_lower = text.lower()
        if "price" in text_lower or "rate" in text_lower or "invoice" in text_lower or "cost" in text_lower:
            primary = "business_rule"
            domain = "Invoices"
        elif "remember" in text_lower or "note" in text_lower:
            primary = "persistent_memory"
            domain = "Personal"
        else:
            primary = "reference_material"
            domain = "General"

        return {
            "primary_intent": primary,
            "domain": domain,
            "is_source_of_truth": "source of truth" in text_lower or "official" in text_lower or "pricing" in text_lower
        }

    def _extract_entities(self, text: str) -> List[Dict[str, Any]]:
        entities = []
        # Pattern extraction for rates ($XX/hr or $XX)
        prices = re.findall(r"\$\d+(?:\.\d{2})?(?:/hr)?", text)
        for p in prices:
            entities.append({"type": "price_item", "value": p})
        return entities

knowledge_ingestor = UniversalKnowledgeIngestor()
