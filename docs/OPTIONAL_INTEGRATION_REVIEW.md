# Optional integration review

These projects informed original implementation and future adapter decisions.
Reviewing a project does not install it, endorse every claim, or establish device
compatibility. No upstream implementation code was copied in this change.

| Project | License reviewed | Useful direction | Decision |
| --- | --- | --- | --- |
| [Pulse](https://github.com/rcourtman/Pulse) | MIT | Service observations, freshness, scoped control | Apply observation and freshness principles; no dependency |
| [TrueForge](https://github.com/truefoundry/trueforge) | MIT | Durable local execution, tools configured separately | Retain Kingdom's own durable runtime; optional adapter |
| [Hermes](https://github.com/NousResearch/hermes-agent) | MIT | Reusable skills and tool execution | Optional harness integration, never a required install |
| [AgentFM](https://github.com/Agent-FM/agentfm-core) | Apache-2.0 | Worker telemetry, signed evidence and role separation | Design reference; no package integration |
| [Ruflo](https://github.com/ruvnet/ruflo) | MIT | Mesh coordination and memory federation | Evaluate scoped protocol adapters rather than import a second orchestrator |
| [Needle](https://github.com/cactus-compute/needle) | Apache-2.0 | Small-model extraction, embeddings and tools | Benchmark on supported devices before adoption |
| [Artemis](https://github.com/google/artemis) | Apache-2.0 | Android observation/action workflows | Optional authorized-device adapter; generic Android box support unproven |
| [MultiPath](https://github.com/uditya-kumar/MultiPath) | MIT | Connection distribution | Optional host networking; not firmware or single-connection bandwidth multiplication |

Before any actual dependency integration, pin the reviewed revision, recheck its
license and notices, inspect transitive dependencies, add independent tests, and
measure its benefit. Projects with uncleared or incompatible distribution terms
are not bundled merely because they are available publicly.
