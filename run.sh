#!/bin/bash
set -e
if ! command -v python3 &>/dev/null; then echo "python3 not found"; exit 1; fi
[ ! -d "venv" ] && python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

if [ "$1" == "--nohup" ]; then
    nohup python cli.py --hidden > /dev/null 2>&1 &
    echo "Process started with PID: $!"
elif [ "$1" == "--hidden" ]; then
    python cli.py --hidden
else
    python cli.py
fi