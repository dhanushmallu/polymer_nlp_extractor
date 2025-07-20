# polymer_extractor/cli/cli.py

from typer import Typer
from polymer_extractor.cli.setup_cli import app as setup_cli_app

cli = Typer(help="Polymer NLP Extractor CLI")

# Add the setup CLI commands under the 'setup' namespace
cli.add_typer(setup_cli_app, name="setup", help="Setup-related commands.")

if __name__ == "__main__":
    cli()