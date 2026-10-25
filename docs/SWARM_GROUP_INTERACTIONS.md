# Swarm groups and native peer analysis

The network view presents one Kingdom containing named computer Knights. It
counts online and disconnected/unknown computers separately. Offline computers
remain visible with a dashed card until the owner's list timeout: seven days by
default, configurable between 12 hours and ten days. Archiving only hides a
computer from the main list; identity, pairing, grants and group membership are
retained. Fresh verified peer reports bring it back automatically.

## Diagram controls

- Drag a Knight onto another Knight to open a named group with both selected.
- Drop onto a group to edit membership; drop onto Ungrouped to remove membership.
- Right-click or select a card for its context menu. Touch/keyboard users can use
  the same action buttons. Work, Apprentice and service reports open in a dialog.
- Make group offers checkboxes for known members. Other-group Knights appear
  last, gray but selectable. Selection asks to move them; bulk selection asks
  once before saving the moves. Canceling a dialog changes nothing.
- Edit name, members, leader, flags and preferred work types in one dialog.
- Combine several groups into one; split into named nonempty groups. Remainders
  go to the first groups. Each split group starts with its first member as leader.
- Dissolve releases members without deleting computers. A move repairs a source
  group's leader if needed, and removes an empty source group.

Backend edits are one SQLite transaction with an expected snapshot version.
Stale screens get a conflict, not an overwrite. A Knight belongs to at most one
organizational group in this controller. Existing overlapping legacy groups must
be resolved explicitly. Group edits do not change grants, workload policy or
operating-system permissions. Groups remain controller-scoped; cross-controller
authoritative group editing is a separate federation feature.

## Actual work consumption

Previously the maintained peer link exchanged heartbeat/inventory data but did
not run a native task consumer. A queued analysis could remain queued despite a
green connection. The connection lifecycle now runs a bounded pure-analysis
consumer after verified reconnection. It needs a running level-five runtime,
an installed coder with compute permission in both local permission stores,
an approved peer compute grant, fresh health, battery and capacity checks.

Only literal text analysis and Python syntax analysis are supported. There is no
shell, model inference, arbitrary code execution, container creation or grant
change in this consumer. It polls at most one supported task, validates exact
assignment/lease/fencing, stores a bounded durable result, and submits a signed
result for independent controller recomputation. An exact repeated lease reuses
the durable result. A failed analysis does not turn a healthy connection red.
Native polls ask the controller to honor its stopped runtime state.

This closes a specific autonomous dispatch gap. It does not demonstrate general
repository editing, independent engineering review, integration testing or
automatic release. Those require their own actual receipts.
