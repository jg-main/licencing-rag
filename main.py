#!/usr/bin/env python3
# main.py
"""CLI entrypoint for the License Intelligence System.

This file is kept for backward compatibility with 'python main.py' usage.
The main logic has been moved to app/cli.py to support the 'rag' command.
"""

from app.cli import main

if __name__ == "__main__":
    import sys
    sys.exit(main())
