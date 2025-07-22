import typer
from pathlib import Path

from polymer_extractor.services.grobid_service import GrobidService
from polymer_extractor.utils.logging import Logger

logger = Logger()
grobid_app = typer.Typer(name="grobid", help="Manage GROBID processing.")

# Initialize GrobidService with the GROBID API URL
GROBID_API_URL = "http://localhost:8070"  # Replace with your actual GROBID API URL
grobid_service = GrobidService(GROBID_API_URL)


@grobid_app.command("status")
def server_status():
    """
    Check GROBID server readiness.
    """
    try:
        grobid_service.check_server_status()
        typer.secho("GROBID server is running and responding.", fg=typer.colors.GREEN)
    except RuntimeError as e:
        typer.secho(f"GROBID server is not running: {e}", fg=typer.colors.RED)


@grobid_app.command("process")
def process_file(path: Path):
    """
    Process a file (PDF/XML/HTML) with GROBID.
    """
    try:
        # Check if the server is running
        grobid_service.check_server_status()

        if not path.exists():
            typer.secho(f"Path does not exist: {path}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        # Process the file
        grobid_service.process_file(path)
        typer.secho(f"Processing complete for: {path}", fg=typer.colors.GREEN)
    except RuntimeError as e:
        typer.secho(f"GROBID processing failed: {e}", fg=typer.colors.RED)
    except Exception as e:
        typer.secho(f"Unexpected error: {e}", fg=typer.colors.RED)