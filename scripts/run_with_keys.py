"""Prompt locally without echoing keys; no files, logs or shell history contain them."""
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
for name in ['DEEPSEEK_API_KEY','OPENROUTER_API_KEY']:
    if not os.environ.get(name):os.environ[name]=getpass.getpass(name+': ').strip()
from sizheng.__main__ import main
main()
