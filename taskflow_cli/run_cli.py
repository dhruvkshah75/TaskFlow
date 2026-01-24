#!/usr/bin/env python3
"""
TaskFlow CLI Entry Point

This script allows running the CLI from the project root without installation.
"""

import sys
from pathlib import Path

# Add the parent directory to the path so we can import taskflow
sys.path.insert(0, str(Path(__file__).parent))

from taskflow.main import run

if __name__ == "__main__":
    run()
