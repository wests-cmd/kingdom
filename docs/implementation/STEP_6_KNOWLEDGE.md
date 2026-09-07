# STEP 6 ARCHITECTURE: UNIVERSAL KNOWLEDGE INGESTION & SOURCE OF TRUTH

Kingdom ingests multi-modal user input (text, PDF, CSV, screenshots, photos, transcripts) through a unified zero-trust pipeline.

## Ingestion Pipeline
1. Input Validation & Prompt Firewall (`PromptFirewall` inspects text for injection attempts).
2. Intent Classification (Classifies text into memory, business rules, or reference material).
3. Entity Extraction (Extracts price items, rates, dates).
4. Namespace Domain Tagging (`Personal`, `Business`, `Finance`, `Invoices`, `Pricing`).
5. Source-Of-Truth Conflict Detection (Identifies conflicting pricing/rule documents and flags for user review).
