# Project Troubleshooting Log

This file is a running log of problems I’ve hit while working on the project, plus how I diagnosed and fixed them.

The goal:  
- Make it easy to **add new problems**.
- Make each entry **useful to future me** (and any other dev).
- Capture **context**, **symptoms**, **root cause**, and **fix**.

---

## How to Use This File

- Each problem is logged under `## Problem N: <short title>`.
- Use the **template** below for any new issue.
- Keep notes **short but specific**: copy error messages, commands, and final fixes.

---

## Problem 1: Fixing `llama.cpp` Shared Library Issues on Linux

**Date:** 2025-11-26  
**Area:** `llama.cpp` / Linux dynamic linking

### Context

I was setting up `llama.cpp` on Linux and trying to run `llama-server` for my local LLM setup.  
The server was being run either directly or via a tmux session, e.g.:

```bash
cd llama.cpp && ./build/bin/llama-server \
  -m ../models/llama-3.2-3b-instruct-q4_k_m.gguf \
  --port 8080
```

### Symptoms

When running `llama-server`, I encountered errors related to shared libraries:

```bash
./build/bin/llama-server: error while loading shared libraries: libllama.so: cannot open shared object file: No such file or directory
``` 
This happened both when running directly in the terminal and inside a tmux session.

### Investigation
I checked which shared libraries `llama-server` was trying to load using `ldd`:

```bash
ldd ./build/bin/llama-server
```
This showed that `libllama.so` was not found. I verified that `libllama.so` existed in the expected directory (`./build/lib/`).

I also checked the `LD_LIBRARY_PATH` environment variable:

```bash
echo $LD_LIBRARY_PATH
```
It was either empty or did not include the path to `libllama.so`.
I tried setting `LD_LIBRARY_PATH` manually:

```bash
export LD_LIBRARY_PATH=$(pwd)/build/lib:$LD_LIBRARY_PATH
```

After setting this, I ran `llama-server` again, and it worked.

### Root Cause
The `llama-server` binary could not find `libllama.so` because the directory containing the library was not included in the `LD_LIBRARY_PATH` environment variable.

### Fix
I added the following line to my shell profile (`~/.bashrc` or `~/.zshrc`):
```bash
export LD_LIBRARY_PATH=/path/to/llama.cpp/build/lib:$LD_LIBRARY_PATH
```
This ensures that every new terminal session (including tmux) has the correct library path set.

### Commands / Snippets

```bash
#!/usr/bin/env bash

set -euo pipefail

SESSION_NAME="llama_servers"

# Directory of this script (robust, even if called via relative path)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Go to llama.cpp so relative paths are sane
cd "${SCRIPT_DIR}/llama.cpp"

# Set up library path for llama-server
export LD_LIBRARY_PATH="$PWD/build/lib:$PWD/build/bin:${LD_LIBRARY_PATH:-}"

# If session already exists, don't create a new one, just attach
if ! tmux has-session -t "${SESSION_NAME}" 2>/dev/null; then
  tmux new-session -d -s "${SESSION_NAME}" \
    "./build/bin/llama-server \
      -m ../models/llama-3.2-3b-instruct-q4_k_m.gguf \
      --port 8080"
fi

tmux attach -t "${SESSION_NAME}"
``` 
---
## Problem 2: MCP tool runs but Firefox won’t open (no DISPLAY in server process)

**Date:** 2025-12-25  
**Area:** MCP (stdio) / Python subprocess env / Selenium

### Context

- I was building a tool in the MCP server that opens a YouTube video using Selenium (Firefox + geckodriver).
- The LLM agent successfully called the MCP tool, but I couldn’t see any browser window.
- Client and server were running on the same machine.

### Symptoms

- Tool call appeared to succeed from the agent side, but Firefox never opened.
- Server logs showed geckodriver starting and then Firefox exiting immediately.
- Exact error:

  `Error: no DISPLAY environment variable specified`

- Command used to verify my shell environment:

  - `echo $DISPLAY` returned `:0`
  - `echo $XDG_RUNTIME_DIR` returned `/run/user/1000`

### Investigation

- Checked that my terminal session had the correct GUI variables:
  - `DISPLAY=:0`
  - `XDG_RUNTIME_DIR=/run/user/1000`
- Looked at MCP server logs and saw that Firefox failed specifically because `DISPLAY` was missing.
- Reviewed the MCP client code that spawns the stdio server and found I was starting it with:

  - `StdioServerParameters(..., env=None)`

### Root Cause

- The MCP server runs as a subprocess started by the client. I spawned it without inheriting my environment (`env=None`), so the server process didn’t receive `DISPLAY` and couldn’t open a GUI Firefox window.

### Fix

- Passed through the current environment when spawning the MCP server subprocess:

  - Changed `env=None` to `env=os.environ.copy()` in `StdioServerParameters`.

- Result: the server inherited `DISPLAY=:0`, and Selenium Firefox opened visibly.

### Commands / Snippets

```python
import os
from mcp import StdioServerParameters

server_params = StdioServerParameters(
    command="python",
    args=[abs_path],
    env=os.environ.copy(),  # inherit DISPLAY/XDG_RUNTIME_DIR so GUI apps can open
)
```

---
## Problem Entry Template

> Copy-paste this section when logging a new problem.

```markdown
## Problem N: <Short, descriptive title>

**Date:** YYYY-MM-DD  
**Area:** <e.g. llama.cpp / tmux / CUDA / Python env / etc.>

### Context

- What I was trying to do.
- Which part of the project this relates to.
- Any relevant environment details (OS, GPU, tool versions, etc.).

### Symptoms

- Exact error messages (copy-pasted).
- What command/script I ran.
- What I expected vs what happened.

### Investigation

- Commands I ran to debug (e.g. `ldd`, `ls`, `grep`, etc.).
- Observations / things I tried.
- Any false leads worth remembering.

### Root Cause

- One or two sentences explaining the *real* underlying cause.

### Fix

- Final steps/commands/config changes that fixed it.
- If there are multiple options, list the one I used first, then alternatives.

### Commands / Snippets

```bash
# Example commands / exports / script snippets used
some_command --with-flags
```


