# Agentic AI: Neuro-Symbolic Agentic Mesh PoC

This project is a Proof of Concept implementation of a sophisticated Agentic AI system.

## Architecture

The system is built on the "Neuro-Symbolic Agentic Mesh" architecture:
- **Cortex**: Orchestration Engine (LangGraph)
- **Hippocampus**: Memory System (Vector/Graph/Episodic)
- **Agent Fabric**: The mesh of specialized agents
- **Evolutionary Layer**: Self-improvement logic

## Setup

1. Clone repository.
2. Create/activate a virtual environment (Python 3.11 preferred).
3. Upgrade packaging tools:
   ```bash
   python -m pip install --upgrade pip setuptools "wheel<0.46"
   ```
4. Install baseline dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. (Optional) Install advanced integrations (browser automation, desktop control, Groq provider):
   ```bash
   pip install -r requirements-optional.txt
   ```
6. (Optional, heavy) Install local embedding fallback dependencies:
   ```bash
   pip install -r requirements-optional-ml.txt
   ```
7. Set up environment variables in `.env`.
8. Run the system: `python main.py`

## Baseline test workflow

This repository includes a stable baseline test suite (fast, no external services):

```bash
python -m pytest
```

To run the broader legacy/integration test set explicitly:

```bash
python -m pytest tests
```

To bootstrap a local environment and run tests in one command:

```bash
./scripts/bootstrap_test_env.sh
```

If you want optional integrations installed during bootstrap:

```bash
INSTALL_OPTIONAL=1 ./scripts/bootstrap_test_env.sh
```

If you also want heavy local-ML dependencies installed during bootstrap:

```bash
INSTALL_OPTIONAL=1 INSTALL_OPTIONAL_ML=1 ./scripts/bootstrap_test_env.sh
```

## Directory Structure

- `cortex/`: State machines and routing logic.
- `hippocampus/`: Memory managers (Vector/Redis).
- `agent_fabric/`: Agent definitions and tools.
- `evolution/`: Self-improvement modules.
- `hippocampus/`: Memory modules (Vector DB).

## Features

### 1. Neuro-Symbolic Architecture
The system uses a `Supervisor` to route tasks between specialized agents:
- **Researcher**: Uses Vector Search (RAG) to find and store information.
- **Coder**: Writes and executes Python code.
- **Architect**: Manages the system itself (file I/O, tool creation).

### 2. Evolution Engine
- **Tool Synthesis**: Ask the Architect to "create a new tool" and it will write the Python code for it.
- **Memory Consolidation**: Run `dream` in the console to distill daily logs into wisdom.

### 3. Self-Healing
- **Error Recovery**: If a tool fails (e.g., missing library), the Supervisor routes the error to the Architect.
- **System Tools**: The Architect can `pip install` packages and `restart_system` to fix the environment.

### 4. OpenRouter Integration
Multi-model support via `config.py`:
- **Thinker**: DeepSeek R1 (Reasoning)
- **Coder**: DeepSeek R1T2 Chimera / Trinity Large (Coding)
- **Memory**: Nemotron-3 (Context)

## Configuration
Edit `.env` to set your keys:
```bash
LLM_PROVIDER=openrouter
LLM_API_KEY=sk-or-v1...
```
