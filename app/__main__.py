"""Allow running app.cli as a module: python -m app.cli"""

from app.cli import cli_main

if __name__ == "__main__":
    cli_main()
