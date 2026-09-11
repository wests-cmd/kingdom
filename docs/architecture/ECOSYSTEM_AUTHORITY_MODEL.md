# Kingdom Ecosystem Authority Model

## Core Principles

1. **Extensibility Without Uncontrolled Authority**: Extensions and integrations provide capabilities; Kingdom backend enforces permissions.
2. **Credential Isolation**: Raw credentials (OAuth tokens, API keys) are held strictly in `CredentialBroker` and are NEVER passed to models, prompts, logs, or UI telemetry.
3. **Model Reasoning vs. Backend Authority**:
   - **AI Reasons**: Proposes tool invocations based on task goals.
   - **Kingdom Authorizes**: Independently validates actor, capability, risk level, and human approval before dispatch.
   - **Knights Execute**: Perform operations within bounded sandbox.
   - **Kingdom Verifies**: Verifies outcome against expected invariants.
