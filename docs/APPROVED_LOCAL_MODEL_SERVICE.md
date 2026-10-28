# Share an existing local planning model

`scripts/serve-approved-local-model.py` is an optional operator-installed TLS
service. It shares one existing loopback Ollama model; it does not install models,
run tools, expose management routes or change Kingdom node grants. A paired Knight
and a configured inference connection remain different authorization mechanisms.

Provision the server certificate through an independently verified host identity.
Give the client the specific trusted certificate using its model profile's
`ca_certificate`, and store a separately generated bearer secret through the
encrypted write-only model credential API. Never disable certificate validation.
Restrict client source addresses; IP filtering alone is not authentication.

The private operator JSON configuration contains `certificate` and `private_key`
paths, a random `token` of at least32 characters, `allowed_ips`, `node_id`, `model`,
`port`, and fixed `upstream: http://127.0.0.1:11435`. Keep its directory0700 and
private files0600. Install a supervised host service with no-new-privileges,
resource limits and restart-on-failure. It needs no Docker access or owner API key.

Allowed endpoints are authenticated health, a live filtered model list, and
non-streaming `/api/chat` or `/api/generate`. The service rejects other models,
tools, unsupported fields and resource requests beyond its bounds. It forces
thinking off, permits one inference at a time, bounds connections/handshakes/body
reads, and does not log prompts or credentials. Model responses remain untrusted
proposals. Their correctness and useful latency require separate measurements.

Renew the server certificate before expiry and update the approved profile through
normal administration. This example does not provide automatic certificate
rotation, discovery after DHCP changes, or node-signed inference RPC. Physical
Knight membership and its revocation policy remain unchanged.
