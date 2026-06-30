"""Flask web server for the Candidate Data Transformer."""

import json
import logging
import tempfile
from pathlib import Path
from typing import List, Dict, Any

from flask import Flask, request, jsonify
from flask_cors import CORS

from transformer.models import ProjectionConfig, load_json_model
from transformer.pipeline import extract, normalize, merge, confidence, project, validate

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)


@app.route("/", methods=["GET"])
def root():
    """API info endpoint."""
    return jsonify({
        "status": "ok",
        "service": "Candidate Data Transformer API",
        "endpoints": {
            "POST /api/transform": "Transform candidate data",
            "GET /api/configs": "List available configs",
            "GET /api/schema": "Get default schema",
            "GET /health": "Health check"
        }
    }), 200


@app.route("/api/transform", methods=["POST"])
def transform():
    """Transform candidate data from uploaded files."""
    try:
        # Check if files and config are provided
        if "files" not in request.files:
            return jsonify({"error": "No files provided"}), 400

        files = request.files.getlist("files")
        if not files:
            return jsonify({"error": "No files selected"}), 400

        config_str = request.form.get("config")
        if not config_str:
            return jsonify({"error": "No config provided"}), 400

        # Parse config JSON
        try:
            config_dict = json.loads(config_str)
            config = ProjectionConfig.model_validate(config_dict)
        except Exception as e:
            return jsonify({"error": f"Invalid config: {str(e)}"}), 400

        # Save uploaded files to temp directory
        temp_files = []
        for file in files:
            if file and file.filename:
                # Save to temp file
                with tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=Path(file.filename).suffix,
                    mode="wb"
                ) as tmp:
                    file.save(tmp.name)
                    temp_files.append(tmp.name)

        if not temp_files:
            return jsonify({"error": "Failed to save uploaded files"}), 400

        # Run pipeline
        logger.info(f"Processing {len(temp_files)} files")

        raw_records = extract(temp_files)
        logger.info(f"Extracted {len(raw_records)} raw records")

        normalized_records = normalize(raw_records)
        logger.info(f"Normalized {len(normalized_records)} records")

        candidates = merge(normalized_records)
        logger.info(f"Merged into {len(candidates)} candidates")

        candidates = confidence(candidates)
        logger.info(f"Computed confidence for {len(candidates)} candidates")

        output = project(candidates, config)
        logger.info(f"Projected {len(output)} results")

        # Validate output
        try:
            validate(output, config)
            logger.info("Output validated successfully")
        except Exception as e:
            logger.warning(f"Validation warning: {e}")

        # Clean up temp files
        for tmp_file in temp_files:
            try:
                Path(tmp_file).unlink(missing_ok=True)
            except Exception as e:
                logger.warning(f"Failed to clean up temp file {tmp_file}: {e}")

        return jsonify({
            "success": True,
            "message": f"Successfully processed {len(output)} candidate(s)",
            "data": output,
            "count": len(output),
        }), 200

    except Exception as e:
        logger.error(f"Transformation error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/configs", methods=["GET"])
def get_configs():
    """Get available config files."""
    try:
        config_dir = Path("configs")
        configs = {}

        for config_file in config_dir.glob("*.json"):
            try:
                with open(config_file, "r") as f:
                    configs[config_file.stem] = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load config {config_file}: {e}")

        return jsonify({"configs": configs}), 200
    except Exception as e:
        logger.error(f"Error getting configs: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/schema", methods=["GET"])
def get_schema():
    """Get the default output schema."""
    try:
        config = load_json_model(ProjectionConfig, "configs/default.json")
        return jsonify({
            "schema": [
                {
                    "path": field.path,
                    "from": field.from_,
                    "type": field.type,
                    "required": field.required,
                }
                for field in config.fields
            ]
        }), 200
    except Exception as e:
        logger.error(f"Error getting schema: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    logger.info("=" * 70)
    logger.info("Starting Candidate Data Transformer API Server")
    logger.info("=" * 70)
    logger.info("API Server Running On http://localhost:5000")
    logger.info("React Frontend Will Run On http://localhost:3000")
    logger.info("Visit http://localhost:3000 In Your Browser")
    logger.info("=" * 70)
    app.run(debug=False, host="0.0.0.0", port=5000)
