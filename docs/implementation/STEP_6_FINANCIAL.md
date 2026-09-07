# STEP 6 ARCHITECTURE: GOVERNED FINANCIAL RESEARCH & BROKER INTEGRATION

Kingdom provides financial research, dividend screening, and broker execution under strict human governance.

## Financial Architecture
1. Market Research & Dividend Screening (`GET /financial/research`). Evaluates valuation, dividend history, free cash flow, and risk factors.
2. Scoped OAuth Broker Connection (`POST /financial/connect`). Scoped tokens for portfolio read & order draft creation (NO PASSWORDS STORED).
3. Draft Order Preview (`POST /financial/order/draft`). Generates order preview and creates an L4 High-Impact Approval Request in `ApprovalEngine`.
4. Explicit Human Approval (`POST /financial/order/{id}/execute`). Orders are blocked until human operator explicitly approves through governance controls.
