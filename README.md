# ARES Agent

ARES is a local desktop AI assistant project built for learning and experimentation. It combines a locally-run LLM, tool-calling via MCP, text-to-speech, and a desktop UI with a state-driven animated orb.

---

## Learning reason

This repository exists as a hands-on learning project for building a local AI agent end-to-end.

The goal is to understand how the parts fit together in a real implementation:

- Running an LLM locally using `llama.cpp` (GGUF models).
- Adding capabilities via tool-calling using the Model Context Protocol (MCP).
- Speaking responses using local TTS (Piper).
- Building a desktop UI using PySide6 + QML (including state-driven animation).
- Debugging real integration issues (process env propagation, GUI display, driver/tool availability, etc.).

The project is intentionally built incrementally so each component can be tested independently.

---

## What does it do

ARES currently supports:

- **Desktop UI**: A QML interface with an animated orb and a prompt input box.
- **Local LLM chat**: The agent takes prompts and produces text responses using a local GGUF model (via `llama.cpp`).
- **Tool calling (MCP)**: The agent can call tools exposed by an MCP server (example tools include YouTube open/play and system stats).
- **Text-to-Speech (Piper)**: The assistant can speak its response using Piper TTS.
- **UI state model**: The backend updates `state` (`idle`, `thinking`, `speaking`, `error`) and the UI reacts via QML property binding.

---

## Setup

### Prerequisites

- Python 3.12+
- `uv` installed
- A local GGUF model file for the agent (e.g., Llama 3.2 3B Instruct)
- A Piper voice model (`.onnx` + matching `.onnx.json`)
- Llama.cpp compiled with GGUF support
- Linux OS (tested on Linux Mint 21/Ubuntu 22.04)

### Install Python dependencies

From the repo root:

```bash
uv sync
```

## Model files

Place your model files in `./models/`:

- **LLM model (GGUF)**, example:
  - `./models/llama-3.2-3b-instruct-q4_k_m.gguf`

- **Piper voice model**, example:
  - `./models/en_GB-northern_english_male-medium.onnx`
  - `./models/en_GB-northern_english_male-medium.onnx.json`

Update the paths in your backend configuration if you use different filenames.

## Run the desktop app

```bash
uv run ./app/main.py
```
