# Model offloading and concurrent chats

Kingdom can run a complete inference request on another computer. Each server loads its own model; this does not combine CPU cores or RAM into a distributed model. Two computers with one inference slot each can process two chats concurrently.

## Configure computers

In **Models → Your model connections**, save one connection per model computer and test it. A remote connection must use HTTPS. A private server certificate can be supplied as a PEM CA; hostname validation remains enabled. Credentials stay encrypted and are never returned by the profile API.

Set **Simultaneous requests** to 1 for a constrained computer. Give connections on the same physical computer the same **Computer name**, including connections using different URL aliases or ports. These share the most conservative configured limit; without a computer name, only identical endpoints share slots. Set the same optional pool name, such as `chat`, on computers you explicitly trust with those prompts. Select **Pool chat** in Tasks to choose an available computer. Explicit profile selection pins a request to that computer.

The pool considers configured capacity, not GPU speed, answer quality, or live free RAM. An unreachable selected computer produces an error; it does not silently resend private input elsewhere. Keep models in a pool compatible with the work and attachments. Image requests only select profiles explicitly marked vision-capable. Small models may be unsuitable for coding even when their connection works.

## External chat clients

The authenticated OpenAI-compatible endpoint is:

```text
POST /workspace/model-chat/{profile-or-pool}/chat/completions
```

For example, a client's base URL can end in `/workspace/model-chat/pool:chat`. Use the Kingdom owner token as its API key. Never publish that token. Tool conversations are forwarded as data; the model endpoint does not execute tool calls or grant authority. Existing execution governance still applies in the client/Kingdom task controller.

Both JSON and SSE clients are supported. Upstream replies are buffered, then emitted as SSE chunks with intact tool calls and usage. This provides compatibility, not token-by-token upstream streaming. Busy computers wait up to 30 seconds, then return HTTP 429; failed provider requests return 502. A disconnected caller should retry only after checking its own turn state.

Chat routing runs in Kingdom's main backend. Open Tasks → Two model chats and select different model computers. There is no separate routing service to launch. Existing desktop data and execution governance remain in place.

Capacity accounting is shared by service instances and threads in one Kingdom process. Use one Kingdom backend process for a shared pool. Multiple backend processes or independent Kingdom installations do not share slot accounting. Default-provider requests that bypass named profiles are not managed by this pool.

## Private model node

Install Ollama on the remote computer using its official distribution. Keep it bound to `127.0.0.1:11434`. Install an appropriately small model and configure its real runtime context window. Hermes currently requires at least 64K context; a connection label cannot increase a model's native capacity or hardware memory.

The optional `scripts/model-node-https.py` provides an authenticated model-only endpoint. It expects these private files in `~/.local/share/kingdom-model-node`:

- `api-token`: randomly generated bearer credential, readable only by the node owner.
- `server-cert.pem`: server certificate with a subjectAltName matching the node's private IP/hostname.
- `server-key.pem`: private key, readable only by the node owner.

Bind it to the node's Tailscale address using `KINGDOM_MODEL_BIND`; the default is loopback. Connect using HTTPS and supply the public CA certificate in the Kingdom profile. The wrapper only forwards model listing and buffered inference to local Ollama; it rejects missing credentials, arbitrary upstream paths and oversized requests. Request and reply limits protect small nodes, and inference uses one CPU thread. Never expose the unauthenticated Ollama port publicly or copy node secrets into Git.

Use a user service or another supervised process. A user service may require login or administrator-enabled lingering to survive logout; verify reboot/logout behavior on the actual machine. Keep laptop nodes powered and awake. Renew certificates before expiration and update the trusted CA when replacing a certificate.

## Validation

Automated tests use actual local HTTP servers to verify two-server concurrency, same-server serialization across service instances, cancellation/failure cleanup, bounded busy waits, vision filtering, authenticated SSE/tool forwarding and rejected invalid certificate/configuration inputs. Live hardware verification is separate: record the actual models, simultaneous in-flight requests, latency and answer quality. Successful routing is not a model-quality certification.
