# Swarm teams and capability controls

The Swarm Network map now includes teams and access controls beside the existing computer map and editable coordination hierarchy.

- A Knight is a computer; an Apprentice is an agent on that computer.
- Lines in the computer map represent pairing, not Ethernet or Wi-Fi topology.
- Moving a coordination line never changes grants or hosting.
- The capability editor uses the existing owner-authenticated node capability API and reads back the result. It changes this controller's authorization for a paired Knight, subject to current identity, policy, tool support and OS permissions. It is not a host firewall, vault-sharing rule, or arbitrary source/destination ACL.
- Only currently approved/connected paired computers may become team members or leaders. Existing team assignment checks constrain a leader to its own currently approved members. Existing tool and approval checks still apply.
- Team creation persists bounded flags and preferred task-type labels in SQLite. These labels are explicitly `planning_only`: they do not change scheduler order or prove automatic placement. The UI states this limitation. A separately enforced directed access-policy editor remains follow-up work.
- Removing a team removes its assignment authority without changing any computer grants. Existing running work is not cancelled by this operation.

No existing computer grants were changed while developing or testing this feature. No new tool execution mechanism or network scan was added.

The separate task-type priority editor is enforceable: owner-authenticated settings persist with a revision check, and the backlog selects higher-priority types first among eligible work, then existing item priority and creation time. Task types are explicit owner labels on new outcomes; they are not guessed from untrusted model text. At most 20 types are configured, each 0–100; unlisted types use 0. This never changes dependencies, leases, required reviewed missions, runtime/autonomy gates or grants, and never preempts a running task. Team preferences do not automatically rewrite those global priorities. Existing outcomes retain their generic type, preserving prior idempotency records.

Validation: persistence, deletion, authority, input-bounds, capability revocation/readback, task-type selection and dependency/policy tests; existing hierarchy/mission/programme tests; production frontend build. Live browser acceptance and real multi-Knight execution remain separate checks for release integration.

