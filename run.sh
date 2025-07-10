#!/bin/bash
set -e
if ! command -v python3 &>/dev/null; then echo "python3 not found"; exit 1; fi
[ ! -d "venv" ] && python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python cli.py "$@" 
