#!/usr/bin/env bash

# Before going to the python code, document this code and see what were the 
# instructions to run the servers and the error you got before that.
# Inspect the code and see if there is something you don't understand.
set -euo pipefail

SESSION_NAME="llama_servers"

# Directory of this script (robust, even if called via relative path)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Go to llama.cpp so relative paths are sane
cd "${SCRIPT_DIR}/llama.cpp"

# LD_LIBRARY_PATH tells the dynamic linker where to look for shared libraries (.so files).
# Here we:
#   1) Prepend the project-specific build directories:
#        - "$PWD/build/lib" : where libllama.so, libmtmd.so, etc. are built
#        - "$PWD/build/bin" : sometimes additional libs/binaries live here
#   2) Append the existing LD_LIBRARY_PATH (if it is set), so we don't lose any
#      previously configured library paths.
#
# ${LD_LIBRARY_PATH:-} means:
#   - If LD_LIBRARY_PATH is set and non-empty, use its value.
#   - If it's unset/empty, substitute an empty string instead (so the expansion doesn't break).
#
# export makes LD_LIBRARY_PATH part of the environment, so any child process
# we start from this shell (like ./build/bin/llama-server) will also see it.
export LD_LIBRARY_PATH="$PWD/build/lib:$PWD/build/bin:${LD_LIBRARY_PATH:-}"

# If session already exists, don't create a new one, just attach
if ! tmux has-session -t "${SESSION_NAME}" 2>/dev/null; then
  tmux new-session -d -s "${SESSION_NAME}" \
    "./build/bin/llama-server \
      -m ../models/llama-3.2-3b-instruct-q4_k_m.gguf \
      --port 8080"
fi

tmux attach -t "${SESSION_NAME}"