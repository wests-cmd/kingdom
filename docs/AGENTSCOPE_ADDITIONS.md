# Kingdom addition requirements

Source: the owner's “AgentScope GitHub Review” chat, confirmed on 2026-10-04. This records the Kingdom-only 55-item list and subsequent accessibility requirements. It is an implementation backlog, not a statement that these features are installed or certified. Existing services must be audited and extended rather than replaced. Permission, verification, recovery and accessibility claims require actual evidence.

Implementation status: see [the progress record](AGENTSCOPE_PROGRESS.md). All requirements below remain open until their full acceptance criteria have evidence.

### Updated Kingdom checklist additions

1. **Self-Repair Engine — P0**  
   Detect → diagnose → contain → sandbox repair → test → approve when necessary → deploy → verify → rollback. Models can propose repairs but cannot weaken Kingdom’s security controls.

2. **Live Update System — P0**  
   Signed updates, staging, compatibility checks, component-level updates, rolling Knight updates, task-aware draining, live health verification and automatic rollback.

3. **Last-Known-Good Recovery — P0**  
   Maintain known-good code, configuration, database/schema and dependency state. Failed repairs or updates automatically revert.

4. **Repair Memory — P1**  
   Remember failure signatures, causes, successful repairs, unsuccessful repairs and validation results so recurring failures don't require rediscovery.

5. **Commander/Team Coordinator — P0**  
   Commander decomposes large objectives into bounded tasks and assigns them to specialized Knights.

6. **Knight Specialization — P1**  
   Knights can advertise roles/capabilities such as coding, research, testing, security, data, browser/API, deployment and verification.

7. **Dynamic Knight Teams — P1 — Herd-inspired**  
   Create temporary teams for a job rather than having every Knight involved in everything.

   Example:

   `Objective → Commander → Coding Knight + Test Knight + Security Knight → Verifier → Result`

8. **Task Delegation Graph — P1 — Herd-inspired**  
   Represent complex objectives as dependency graphs:

   `Goal → Task A → Task B/C → Task D → Verification`

   Independent tasks can run simultaneously.

9. **Shared Team State — P1 — Herd-inspired**  
   Knights working on the same objective receive a controlled shared workspace containing task state, approved context, artifacts, results and dependencies.

   Do **not** simply dump every Knight's entire context into every other Knight.

10. **Structured Knight Handoffs — P1 — Herd-inspired**  
    Standardize handoffs:

    `task_id`
    `objective`
    `inputs`
    `constraints`
    `capabilities`
    `artifacts`
    `result`
    `confidence`
    `verification`
    `next_action`

11. **Automatic Task Reassignment — P1 — Herd-inspired**  
    If a Knight crashes, times out, loses its model or becomes unhealthy, Kingdom can reassign its unfinished task after checking leases and fencing the previous worker.

12. **Parallel Execution — P1 — Herd-inspired**  
    Allow independent Knights to work simultaneously rather than forcing every workflow through a serial chain.

13. **Result Aggregator — P1 — Herd-inspired**  
    Combine multiple Knight outputs into one structured result while preserving provenance.

14. **Independent Verifier Knight — P0**  
    A Knight shouldn't certify its own important work. High-risk workflows can use:

    `Builder → Tester → Security Reviewer → Verifier`

15. **Disagreement Resolution — P1**  
    When Knights/models disagree, preserve their evidence and route the disagreement through deterministic rules or human review instead of blindly majority-voting.

16. **Knight Spawn/Retire Lifecycle — P1 — Herd-inspired**  
    Create temporary workers for specific jobs and retire them afterward. Temporary workers receive only the capabilities necessary for that assignment.

17. **Knight Resource Budgets — P1**  
    Every Knight gets limits for CPU, RAM, GPU, tokens, model calls, network, filesystem, time and monetary cost.

18. **Smart Workload Scheduler — P1**  
    Choose Knights using capability + trust + hardware + current load + model availability + locality + cost.

19. **Task Checkpoints — P0**  
    Long-running jobs periodically persist recoverable state so another Knight can resume after failure.

20. **Persistent Workflow Engine — P0**  
    Work survives process restarts, Commander failures and temporary network outages.

21. **Deterministic SOP Engine — P0**  
    Reusable workflows with steps, dependencies, approvals, retries, verification and rollback.

22. **Workflow Templates — P1**  
    Reusable patterns such as:

    `Research → Analyze → Build → Test → Security Review → Verify → Approval → Deploy`

23. **Human-in-the-Loop Workflow Steps — P0**  
    Workflows can stop at defined approval points instead of asking the user about every harmless operation.

24. **Capability Engine — P0**  
    Fine-grained, scoped, expiring and revocable permissions for Knights, workflows and tools.

25. **Central Approval Engine — P0**  
    Sensitive/destructive operations remain governed by Kingdom. Neither Herd-style workers nor models can approve themselves.

26. **Policy Enforcement Middleware — P0**  
    Critical execution follows:

    `Identity → Capability → Policy → Approval → Execution → Verification → Audit`

27. **Governed Model Router — P0**  
    Dynamically select Ollama/cloud/specialist models based on privacy, task complexity, hardware, cost, availability and policy.

28. **Model Fallback — P1**  
    If one model is unavailable, retry through another compatible model without bypassing privacy/security restrictions.

29. **MCP Gateway — P1**  
    Central controlled MCP interoperability rather than letting arbitrary agents directly connect to MCP servers.

30. **A2A Gateway — P1**  
    Communicate with external agents through Kingdom identity, capability and policy boundaries.

31. **Secure Tool Gateway — P0**  
    Filesystem, shell, browser, APIs, Git, packages and other tools remain deterministic controlled execution surfaces.

32. **AI Skill Maps — P1**  
    Import/export/version workflows and skills with dependencies, provenance, signatures, capabilities and compatibility.

33. **Skill Quarantine — P0**  
    Unknown skills run in isolation before trust elevation.

34. **Skill Sandbox Testing — P0**  
    Test imported skills against prompt injection, malicious code, filesystem abuse, network abuse and excessive resource consumption.

35. **Profiles — P1**  
    Developer, Automation, Research, Local AI, Server, Business, Minimal and other profiles simplify setup without weakening security.

36. **API Catalog — P1**  
    Search/discover APIs and associate them with profiles, Skill Maps and workflows.

37. **Node Registry — P0**  
    Real node enrollment, identity, capabilities, heartbeat, health and lifecycle.

38. **Lease + Fencing System — P0**  
    Prevent stale Knights from continuing to execute after reassignment or network partitions.

39. **Commander Failover — P0**  
    Commander failure must not destroy task state or allow two Commanders to control the same operation.

40. **Offline/Partition Recovery — P0**  
    Queue appropriate work but revalidate capabilities and approvals after reconnection.

41. **Prompt Firewall — P0**  
    Webpages, files, Skill Maps, MCP servers, external agents and model responses remain untrusted input.

42. **Credential Broker — P0**  
    Models receive credential references rather than raw secrets whenever possible.

43. **Memory Governance — P1**  
    Separate operational state, task context, durable knowledge, skill knowledge and audit history.

44. **Event Bus — P1**  
    Standard events across Knights, workflows, tools, models, repairs, updates and security.

45. **Live Task Stream — P1 — Herd-inspired**  
    Expose exactly what the swarm is doing:

    `Objective`
    → `Planning`
    → `6 tasks`
    → `4 Knights active`
    → `2 complete`
    → `1 verification`
    → `1 waiting approval`

46. **Execution Tree — P1 — Herd-inspired**  
    Let the user inspect the complete parent/child relationship between objectives, Knights, model calls, tools and results.

47. **OpenTelemetry — P1**  
    Distributed tracing across:

    `User → Commander → Workflow → Knight → Model → Tool → Result → Verifier`

48. **Real Health Engine — P0**  
    Report actual process/database/network/model/Knight/storage health rather than synthetic “healthy” states.

49. **Security Center — P1**  
    Central view of capabilities, approvals, quarantines, credentials, suspicious behavior and blocked actions.

50. **Recovery Center — P1**  
    Show failures, repair attempts, update failures, quarantined components, rollback state and last-known-good state.

51. **Update Dashboard — P1**  
    Current version, candidate version, affected components, rollout progress, Knights remaining, tests and rollback status.

52. **Doomsday Tests — P0**  
    Continue the existing suite and add Commander split-brain, Knight crash during handoff, stale worker execution, corrupted shared state, malicious Knight, poisoned task result, repair loops, failed updates and compromised MCP/skills.

53. **Multi-Agent Chaos Tests — P0 — Herd-inspired**  
    Specifically attack the new team system:

    `Knight disappears`
    `Knight lies`
    `Knight duplicates work`
    `Knight produces malformed output`
    `Knight exceeds capability`
    `Knight ignores cancellation`
    `Knight returns malicious instructions`
    `two Knights claim same task`
    `Commander crashes`
    `network partitions team`

54. **Truth Tests — P0**  
    Detect fake/hard-coded version, node, hardware, model, task, health or release information.

55. **Release Certification Gate — P0**  
    Kingdom does not release unless unit, integration, distributed, multi-agent, security, Doomsday, update, repair, rollback, migration and packaging tests pass.

### The resulting Kingdom architecture

The major change from the Herd ideas is that Kingdom becomes capable of creating **temporary coordinated teams of Knights**:

**User/External Request**  
↓  
**Kingdom Authority**  
↓  
**Identity + Policy + Capability + Approval**  
↓  
**Commander**  
↓  
**SOP / Task Graph**  
↓  
**Team Coordinator**  
↓  
**Specialized Knights**  
↙ ↓ ↘  
Coding / Research / Security / Testing / API / etc.  
↓  
**Result Aggregator**  
↓  
**Independent Verification**  
↓  
**Kingdom Policy Check**  
↓  
**Commit Result + Memory + Audit**

And surrounding the whole thing:

**Live Updates + Self Repair + Last-Known-Good + Rollback + Telemetry + Doomsday Testing.**

That is the direction I'd use for Kingdom: take Herd/AgentScope-style orchestration ideas, but put **Kingdom's deterministic authority layer above all of them**, rather than allowing an agent framework to become the authority itself.

Yes. I would make accessibility a **first-class Kingdom subsystem**, not just larger text in the UI. W3C's guidance for non-web software specifically calls out visual, auditory, cognitive/neurological, physical, and speech disabilities, so Kingdom should design for those categories from the beginning. 

Add this section to the Kingdom master checklist:

## 56. Accessibility & Adaptive Interaction System — P0/P1

Kingdom should have **Settings → Accessibility**, with settings stored per user rather than per device where practical.

### Part 1 — Accessibility Setup Wizard — P0

During first-run, ask:

> **Do you want to configure accessibility options?**

Then offer large, obvious choices such as **Vision**, **Hearing**, **Mobility**, **Speech**, **Reading & Learning**, **Attention & Cognitive**, and **No changes**.

Don't require someone to identify or disclose a medical diagnosis.

### Part 2 — Vision — P0

Add adjustable text size, interface scaling, high contrast, light/dark themes, color-blind-safe palettes, configurable focus indicators, large cursor/pointer, reduced transparency, reduced visual clutter and zoom/magnification compatibility.

Kingdom should never communicate **Approved / Warning / Failed / Running** through color alone. Windows accessibility guidance likewise emphasizes sufficient contrast, scalable text, semantic text roles and compatibility with magnification. 

### Part 3 — Screen Reader Support — P0

Every Kingdom control needs an accessible name, role, state and description.

For example, don't expose:

> "red button"

Expose:

> "Emergency Stop — button — stops active Kingdom execution."

Task progress, Knight status, approval dialogs, errors, repair status and update progress must all be readable without looking at the screen.

### Part 4 — Complete Keyboard Operation — P0

**Everything** must work without a mouse.

That includes navigation, approvals, task creation, settings, emergency stop, update controls, recovery, dialogs and Knight management.

Provide customizable keyboard shortcuts and visible focus indicators.

### Part 5 — Voice Control — P1

A user with limited hand mobility should be able to operate Kingdom by voice:

> "Open approvals."  
> "Read this request."  
> "Go back."  
> "Show active Knights."  
> "Pause task 12."  
> "Increase text size."

Voice-only computer interaction is already practical—Windows Voice Access, for example, supports application navigation and text authoring without requiring continued internet access after setup. 

But **voice is an input method, not increased authority**.

A destructive voice command still passes through:

**Voice → Intent → Identity → Capability → Policy → Confirmation/Approval → Execution → Audit**

### Part 6 — Switch / Limited-Mobility Navigation — P1

Design controls so someone using adaptive switches or very limited movement can operate Kingdom.

Include sequential scanning, large interaction targets, adjustable dwell timing, no drag-only operations, no rapid-click requirements and alternatives to complicated gestures.

### Part 7 — Eye-Control Compatibility — P1

Kingdom doesn't necessarily need to build its own eye tracker. It should expose its UI correctly enough for existing assistive technology.

Windows already supports eye-controlled pointing, clicking, scrolling, keyboard input and text-to-speech. 

That means Kingdom needs large predictable targets and must avoid tiny unlabeled icons.

### Part 8 — Hearing Accessibility — P0

Never make audio the only indication that something happened.

Every spoken/audio notification gets a visual equivalent.

For example:

**Knight completed task**

should support:

`Sound + visual notification + Activity entry`

Critical alerts can optionally flash the appropriate interface region, but flashing effects must themselves be configurable/disableable.

### Part 9 — Captions / Transcripts — P1

Any Kingdom voice interaction should optionally display live text.

Keep an accessible transcript:

**You:** Check node 4.  
**Kingdom:** Node 4 stopped responding 38 seconds ago.  
**You:** Diagnose it.  
**Kingdom:** Starting diagnostics.

Users should be able to interact entirely through text even when voice features exist.

### Part 10 — Speech Disabilities — P1

Never assume spoken input is necessary.

Everything available through speech must also be available through keyboard, switch, touch or another accessible input path.

Kingdom's text interface should have feature parity with voice.

### Part 11 — Cognitive Accessibility — P0

This is particularly important for Kingdom because it can become technically complicated.

Add a **Simplified Interface**.

Instead of:

> RPCSecureTransport validation failed: sender identity does not satisfy registry binding.

Default simple explanation:

> **Kingdom couldn't verify this device.**

Then:

> **Recommended action: Keep the device disconnected.**

And provide:

**Show technical details**

for advanced users.

### Part 12 — Reading Assistance — P1

Provide optional plain-language explanations, shorter paragraphs, increased spacing, readable fonts, text-to-speech, "Explain this" controls and adjustable information density.

For example:

**Technical**

> Node quarantined following identity verification failure.

**Simple**

> Kingdom blocked this computer because it couldn't prove who it was.

Same event. Different presentation.

### Part 13 — Attention / Reduced Distraction Mode — P1

Provide:

**Focus Mode**

It can hide nonessential animations, secondary telemetry, decorative background activity, unnecessary notifications and noncritical live events.

Show only:

**Current task → Important status → Required action**

### Part 14 — Reduced Motion — P0

Every animation should respect **Reduce Motion**.

That includes Knight movement, task graphs, loading animations, live-update animations, transitions and background effects.

Functional information must remain understandable when animations are completely disabled.

### Part 15 — Adjustable Timing — P0

Don't assume everyone can respond quickly.

Accessibility settings should control notification duration, dialog timeouts, voice-response delays, double-click timing where relevant and scanning/dwell timing.

**Security approvals should not silently approve because a timer expired.**

Expiration means:

**approval expired → action denied/pending**

never:

**approval expired → execute anyway**

### Part 16 — Accessible Approval Center — P0

This is particularly important.

Every approval should be understandable through screen reader, keyboard, voice and simplified mode.

For example:

> **Kingdom wants permission to install an update.**
>
> Risk: Medium  
> Changes: 14 files  
> Restart required: Yes  
> Data deletion: No
>
> **Approve / Deny / Explain / Technical Details**

Someone shouldn't need to understand Git diffs to safely operate Kingdom.

### Part 17 — Accessible Self-Repair — P0

When Self Repair detects something:

> **Kingdom found a problem.**
>
> A Knight stopped responding.
>
> Kingdom can restart it safely.
>
> **Repair / Ignore / Explain**

Advanced mode can show the diagnostic evidence, logs, lease state and proposed repair.

### Part 18 — Accessible Live Updates — P0

The Live Update system we just designed should have the same approach:

> **Kingdom 1.7 is ready.**
>
> Security update included.  
> Your settings will remain unchanged.  
> Kingdom will restart once.  
> Automatic rollback is available.
>
> **Update / Later / Explain**

Then expose the technical manifest underneath for advanced users.

### Part 19 — Accessibility Profiles — P1

Allow reusable presets such as:

**Low Vision**
- large text
- large controls
- high contrast
- strong focus indicators

**Screen Reader**
- optimized navigation order
- verbose accessible labels
- reduced decorative content

**Limited Mobility**
- large targets
- keyboard/voice navigation
- extended timing
- no drag requirements

**Cognitive / Simple**
- simplified language
- fewer controls
- step-by-step workflows
- confirmations

**Reduced Distraction**
- minimal animation
- fewer notifications
- simplified dashboard
- focus mode

And then allow every setting to be customized individually.

### Part 20 — Adaptive AI Explanations — P1

Kingdom's models can adapt **presentation**, not authority.

For example, a user could choose:

`Concise`
`Plain language`
`Step-by-step`
`Technical`
`Read aloud`

The underlying policy decision remains identical.

### Part 21 — Emergency Accessibility — P0

**Emergency Stop must always be accessible.**

It needs keyboard access, assistive-technology labeling, large-target access and an optional voice route with appropriate confirmation.

A person should never be locked out of stopping Kingdom because they cannot use a mouse.

### Part 22 — Accessibility Must Survive Failure — P0

This is easy to overlook.

Accessibility cannot disappear when Kingdom enters:

**Recovery Mode / Safe Mode / Lockdown / Update / Rollback / Self Repair**

Those are exactly the situations where the user most needs clear controls.

### Part 23 — Accessibility Settings Sync — P1

Accessibility preferences should survive Kingdom updates and repairs.

Self Repair must **not "fix" accessibility settings back to defaults**.

Updates should explicitly test migration of these preferences.

### Part 24 — Accessibility Testing — P0

Add it to the release gate alongside Doomsday/security tests.

Test at minimum:

**keyboard-only → screen reader semantics → 200%+ text scaling → high contrast → reduced motion → no audio → no mouse → simplified interface → voice navigation → update flow → repair flow → approval flow → emergency stop.**

Accessibility regressions in critical workflows should block release.

---

That also changes one of our fundamental Kingdom design rules.

We already have:

**Human > Governance > Security > Execution > Models**

I'd add a UX rule alongside it:

> **Different abilities may change how Kingdom communicates with the human, but never whether that human retains control.**

So **Self Repair, Live Updates, Commander/Knights, Profiles, Approvals, Recovery, Emergency Stop and every future Kingdom feature must all go through the Accessibility Layer from the beginning**, rather than accessibility being bolted on after Kingdom is finished.
