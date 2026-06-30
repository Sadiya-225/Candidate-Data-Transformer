"""Command-line interface for the candidate transformer."""

import logging
import sys
import json
from pathlib import Path
from typing import List, Optional

import click

from transformer.models import ProjectionConfig, load_json_model
from transformer.pipeline import detect, extract, normalize, merge, confidence, project, validate

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@click.group()
def cli():
    """Candidate Data Transformer."""
    pass


@cli.command()
@click.option(
    "--sources",
    multiple=True,
    required=True,
    help="Source files or URIs (CSV, JSON, PDF, DOCX, TXT, GitHub URL, etc.)",
)
@click.option(
    "--config",
    type=click.Path(exists=True),
    required=True,
    help="Path to projection config JSON",
)
@click.option(
    "--out",
    type=click.Path(),
    required=True,
    help="Output file path (JSON)",
)
@click.option(
    "--pretty",
    is_flag=True,
    default=False,
    help="Pretty-print output JSON",
)
@click.option(
    "--strict",
    is_flag=True,
    default=False,
    help="Treat warnings as errors",
)
def run(
    sources: List[str],
    config: str,
    out: str,
    pretty: bool,
    strict: bool,
):
    """Run the transformation pipeline end-to-end."""
    try:
        logger.info(f"Starting transformation pipeline with {len(sources)} sources")

        # Load config
        config_obj = load_json_model(ProjectionConfig, config)
        logger.info(f"Loaded config from {config}")

        # Run pipeline stages
        logger.info("Stage 1: EXTRACT")
        raw_records = extract(list(sources))
        logger.info(f"  Extracted {len(raw_records)} raw records")

        logger.info("Stage 2: NORMALIZE")
        normalized_records = normalize(raw_records)
        logger.info(f"  Normalized {len(normalized_records)} records")

        logger.info("Stage 3: MERGE")
        candidates = merge(normalized_records)
        logger.info(f"  Merged into {len(candidates)} candidates")

        logger.info("Stage 4: CONFIDENCE")
        candidates = confidence(candidates)

        logger.info("Stage 5: PROJECT")
        projected = project(candidates, config_obj)
        logger.info(f"  Projected {len(projected)} candidates")

        logger.info("Stage 6: VALIDATE")
        projected = validate(projected, config_obj)
        logger.info(f"  Validated {len(projected)} candidates")

        # Write output
        output_path = Path(out)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            if pretty:
                json.dump(projected, f, indent=2)
            else:
                json.dump(projected, f)

        logger.info(f"Output written to {output_path}")

        # Print summary
        click.secho("\n=== TRANSFORMATION COMPLETE ===", fg="green", bold=True)
        click.echo(f"Processed {len(sources)} sources")
        click.echo(f"Generated {len(projected)} candidate profiles")
        click.echo(f"Output: {output_path}")

    except Exception as e:
        error_msg = f"Pipeline failed: {e}"
        logger.error(error_msg)

        if strict:
            click.secho(f"ERROR: {error_msg}", fg="red", bold=True)
            sys.exit(1)
        else:
            click.secho(f"WARNING: {error_msg}", fg="yellow")
            sys.exit(0)


def main():
    """Entry point for CLI."""
    cli()


if __name__ == "__main__":
    main()
