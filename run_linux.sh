#!/bin/bash

PY_EXE=

# Check if python3 is available
if command -v python3 &> /dev/null; then
    PY_EXE="python3"
# Check if python is available (Python 2)
elif command -v python &> /dev/null; then
    PY_EXE="python"
else
    print_msg "Python not found"
    exit 1
fi

$PY_EXE  src/proc.py
