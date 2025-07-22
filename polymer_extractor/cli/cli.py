# polymer_extractor/cli/cli.py

from typer import Typer

# CHANGE THESE LINES:
from .grobid_cli import grobid_app # Changed from 'from cli.grobid_cli'
from .setup_cli import setup_app   # Changed from 'from cli.setup_cli'

cli = Typer(help="Polymer NLP Extractor CLI")

# Add the setup CLI commands under the 'setup' namespace
cli.add_typer(setup_app, name="setup", help="Setup-related commands.")
cli.add_typer(grobid_app, name="grobid", help="GROBID server management commands.")

if __name__ == "__main__":
    cli()