# Kingdom v25.4

Kingdom is a self-organizing, multi-agent AI system designed to start simple
and evolve into a distributed intelligence network.

It is built around three core roles:

- Commander (control + orchestration)
- Knights (worker agents)
- System Core (debate, market, memory, validation)

Everything lives in a single repository so you can clone once, answer a few
questions, and have a working system.

---

## Core Capabilities

### Dynamic Swarm Formation
Knights automatically group into temporary teams based on task needs.
They dissolve after execution and reform based on success patterns.

### Swarm Debate Engine
Before executing a task, Knights generate competing plans, evaluate each
other, and select the best strategy.

### Task Market System
Knights bid on tasks using cost, time, and confidence.
The system selects the most efficient executor.

### Minds Loop (Memory System)
The system learns from successful executions and adapts over time.
Low-confidence results are ignored to prevent bad learning.

### Validation Layer
Multiple agents or models verify outputs before final execution.

### System Control Levels (1–5)
Defines how autonomous the system is, from manual control to full autonomy.

---

## AI Integration

Kingdom supports:

- Local models via Ollama
- Claude Code integration
- OpenClaw-style system control
- Hybrid mode (local + cloud)

---

## Setup

```bash
git clone https://github.com/wests-cmd/kingdom
cd kingdom
python kingdom_setup.py
