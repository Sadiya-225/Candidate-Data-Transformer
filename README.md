# Candidate Data Transformer

A production-quality multi-source candidate data transformer that ingests candidate data from multiple messy sources, normalizes and merges it into a canonical profile per candidate, attaches provenance + confidence to every field, and can re-project that canonical record into a custom schema defined by a runtime config - with no code changes.

## Quick Start

### Prerequisites

- Python 3.10+
- pip

### Installation

```bash
# Clone the repository
cd Candidate-Data-Transformer

# Install dependencies
pip install -r requirements.txt

# Or install in development mode
pip install -e .
```

### Basic Usage

```bash
# Transform single CSV source with default config
python -m transformer run \
  --sources data/sample_inputs/recruiter.csv \
  --config configs/default.json \
  --out output/profiles.json \
  --pretty

# Transform multiple sources (use --sources multiple times)
python -m transformer run \
  --sources data/sample_inputs/recruiter.csv \
  --sources data/sample_inputs/ats.json \
  --config configs/default.json \
  --out output/profiles.json \
  --pretty

# Transform with lean CRM config
python -m transformer run \
  --sources data/sample_inputs/recruiter.csv \
  --config configs/lean_crm.json \
  --out output/lean_profiles.json

# Run with strict mode (warnings = errors)
python -m transformer run \
  --sources data/sample_inputs/recruiter.csv \
  --config configs/default.json \
  --out output/profiles.json \
  --strict
```

### Web User Interface (Modern React + Material UI)

The Project Includes A Modern React Frontend With Material UI Components. To Use It:

#### Backend Setup

```bash
# Terminal 1: Start The Flask Backend Server
python run_web_server.py
# Server Will Run On http://localhost:5000
```

#### Frontend Setup

```bash
# Terminal 2: Install Frontend Dependencies
cd frontend
npm install

# Start The React Development Server
npm start
# Frontend Will Open At http://localhost:3000
```

## Supported Sources

### Structured Sources

1. **Recruiter CSV** (`*.csv`)
   - Columns: `name`, `email`, `phone`, `current_company`, `title`
   - Example: [data/sample_inputs/recruiter.csv](data/sample_inputs/recruiter.csv)

2. **ATS JSON** (`*.json`, semi-structured)
   - Field names: `candidateName`, `contactEmail`, `phoneNumbers[]`, `employer`, `jobTitle`, `skillTags[]`, `workHistory[]`
   - Example: [data/sample_inputs/ats.json](data/sample_inputs/ats.json)

### Unstructured Sources

3. **GitHub Profile** (`github:username` or `https://github.com/username`)
   - Fetches public profile via REST API
   - Infers skills from repo languages and topics
   - Optional: Pass `GITHUB_TOKEN` env var for higher rate limits (60→5000 req/hr)

4. **LinkedIn Profile** (pre-scraped JSON fixture)
   - Limited to local fixture files (no live scraping - ToS restriction)
   - Accept profile JSON/HTML snapshot as local file
   - Documented limitation (see [Assumptions & Limitations](#assumptions--limitations))

5. **Resume (PDF)** (`*.pdf`)
   - Text extraction + regex heuristics
   - Infers: name, emails, phones, skills, experience, education

6. **Resume (DOCX)** (`*.docx`)
   - Text extraction from Word documents
   - Same parsing heuristics as PDF

7. **Recruiter Notes** (`*.txt`)
   - Free-text regex heuristics
   - Extracts: skill mentions, company names, job titles, years of experience hints

## Pipeline Architecture

```
INPUT → DETECT → EXTRACT → NORMALIZE → MERGE → CONFIDENCE → PROJECT → VALIDATE → OUTPUT
```

### Stages

| Stage          | Input                  | Output                    | Purpose                                 |
| -------------- | ---------------------- | ------------------------- | --------------------------------------- |
| **DETECT**     | File path or URI       | Adapter                   | Identify source type                    |
| **EXTRACT**    | Raw source             | RawRecord                 | Parse into intermediate format          |
| **NORMALIZE**  | RawRecord              | NormalizedRecord          | Apply per-field normalizers             |
| **MERGE**      | NormalizedRecord[]     | Candidate[]               | Entity resolution + conflict resolution |
| **CONFIDENCE** | Candidate[]            | Candidate[] (with scores) | Compute confidence/provenance           |
| **PROJECT**    | Candidate[] + Config   | Output dict[]             | Transform to configured schema          |
| **VALIDATE**   | Output dict[] + Config | Output dict[]             | JSON-schema validation                  |

### Normalized Formats

| Field   | Format              | Example                                                          |
| ------- | ------------------- | ---------------------------------------------------------------- |
| Phone   | E.164               | `+14155552671`                                                   |
| Date    | YYYY-MM             | `2023-05`                                                        |
| Country | ISO-3166 alpha-2    | `US`, `GB`, `DE`                                                 |
| Email   | lowercase, RFC 5322 | `john@example.com`                                               |
| Skills  | canonical names     | Canonical from [skills_taxonomy.json](data/skills_taxonomy.json) |
| Name    | Title-case (smart)  | `John McDonald`, `Jean van der Berg`                             |

## Canonical Schema

The internal representation (after MERGE) is a Pydantic `Candidate` model:

```python
{
  "candidate_id": "uuid5-hash",
  "full_name": "string",
  "emails": ["string[]"],
  "phones": ["+E.164"],
  "location": {
    "city": "string",
    "region": "string",
    "country": "ISO-3166-alpha-2"
  },
  "links": [
    {"type": "string", "url": "string"}
  ],
  "headline": "string",
  "years_experience": "float",
  "skills": [
    {
      "name": "string",
      "confidence": "0.0–1.0",
      "canonicalized": "bool",
      "sources": ["string[]"]
    }
  ],
  "experience": [
    {
      "company": "string",
      "title": "string",
      "start": "YYYY-MM",
      "end": "YYYY-MM",
      "summary": "string",
      "source": "string"
    }
  ],
  "education": [
    {
      "institution": "string",
      "degree": "string",
      "field": "string",
      "end_year": "YYYY",
      "source": "string"
    }
  ],
  "provenance": [
    {
      "field": "string",
      "value": "any",
      "sources": [{"source_name": "string", "extraction_method": "string", "confidence": "float"}],
      "final_confidence": "float",
      "extraction_method": "string"
    }
  ],
  "overall_confidence": "0.0–1.0"
}
```

## Configuration & Projection

Output shape is controlled by a runtime config (JSON) with no code changes.

### Config Format

```json
{
  "version": "1.0",
  "fields": [
    {
      "path": "output_key",
      "from": "canonical_path_expr",
      "type": "string|number|object|string[]|object[]",
      "required": true|false,
      "normalize": "E164|canonical",
      "include_confidence": true|false,
      "include_provenance": true|false
    }
  ],
  "include_confidence": true|false,
  "include_provenance": true|false,
  "on_missing": "null|omit|error"
}
```

### Path Expression Syntax

| Expression    | Example                | Meaning                 |
| ------------- | ---------------------- | ----------------------- |
| Dotted path   | `location.country`     | Nested field            |
| Array index   | `emails[0]`            | First element           |
| Array flatten | `skills[].name`        | Extract field from each |
| Combination   | `experience[].company` | Company from each job   |

### Example Configs

**Default config** ([configs/default.json](configs/default.json))

- Full canonical schema + provenance + confidence
- All fields included

**Lean CRM config** ([configs/lean_crm.json](configs/lean_crm.json))

- Minimal fields: `full_name`, `primary_email`, `primary_phone`, `skills`, `years_experience`, `country`
- For CRM integration

## Conflict Resolution Policy

When a candidate appears in multiple sources with conflicting values:

| Field Group                        | Priority (high → low)                                    | Rationale                  |
| ---------------------------------- | -------------------------------------------------------- | -------------------------- |
| Contact (email, phone, location)   | ATS > Recruiter CSV > Resume > LinkedIn > GitHub > Notes | ATS = employer record      |
| Employment (company, title, dates) | Resume > LinkedIn > ATS > Notes > Recruiter CSV          | Resume = official history  |
| Skills, Languages                  | GitHub > Resume > LinkedIn > ATS > Recruiter CSV > Notes | GitHub = demonstrated code |
| Headline, Bio                      | LinkedIn > GitHub > Resume > Notes                       | LinkedIn = curated summary |
| Years Experience                   | Resume (date-derived) > LinkedIn > ATS > Notes > GitHub  | Resume = authoritative     |

**For list fields** (emails, phones, skills, experience, education): **union + dedupe** (all sources merged).

See [data/merge_policy.json](data/merge_policy.json) for the configurable policy.

## Example Output

### Default Config Output

```json
[
  {
    "candidate_id": "550e8400-e29b-41d4-a716-446655440000",
    "full_name": "Alice Johnson",
    "emails": ["alice.johnson@example.com"],
    "phones": ["+14155552671"],
    "location": {
      "city": "San Francisco",
      "region": "CA",
      "country": "US"
    },
    "links": [
      {"type": "github", "url": "https://github.com/alice"}
    ],
    "headline": "Senior Software Engineer",
    "years_experience": 7.5,
    "skills": [
      {"name": "Python", "confidence": 0.95, "canonicalized": true, "sources": ["resume"]},
      {"name": "Kubernetes", "confidence": 0.9, "canonicalized": true, "sources": ["github"]}
    ],
    "experience": [
      {
        "company": "TechCorp",
        "title": "Senior Engineer",
        "start": "2021-05",
        "end": null,
        "summary": null,
        "source": "resume"
      }
    ],
    "education": [
      {
        "institution": "UC Berkeley",
        "degree": "Bachelor",
        "field": "Computer Science",
        "end_year": "2015",
        "source": "linkedin"
      }
    ],
    "provenance": [...],
    "overall_confidence": 0.85
  }
]
```

### Lean CRM Output

```json
[
  {
    "full_name": "Alice Johnson",
    "primary_email": "alice.johnson@example.com",
    "primary_phone": "+14155552671",
    "skills": ["Python", "Kubernetes"],
    "years_experience": 7.5,
    "country": "US",
    "overall_confidence": 0.85
  }
]
```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_normalizers.py -v

# Run integration tests
pytest tests/test_integration.py -v

# Run with coverage report
pytest tests/ --cov transformer --cov-report html
```

**Test Results**:

- 65 tests passing
- 100% success rate
- 0 deprecation warnings
- Coverage report: `htmlcov/index.html` with line-by-line analysis

## Writing Custom Configs

To create a custom projection:

1. Start with [configs/default.json](configs/default.json) or [configs/lean_crm.json](configs/lean_crm.json)
2. Modify `fields[]` to include/exclude and rename fields
3. Set path expressions using `from` (supports dotted paths, array indices, array flattening)
4. Set `on_missing` behavior (`null`, `omit`, `error`)
5. Toggle `include_confidence` and `include_provenance` as needed

Example: Export only name and email for a simple contact list:

```json
{
  "version": "1.0",
  "fields": [
    { "path": "name", "from": "full_name", "type": "string", "required": true },
    { "path": "email", "from": "emails[0]", "type": "string", "required": true }
  ],
  "include_confidence": false,
  "include_provenance": false,
  "on_missing": "error"
}
```

## Design Document

See [DESIGN.md](DESIGN.md) for the architecture, schema decisions, conflict resolution policy, edge case handling, and implementation notes.

## Project Structure

```
Candidate-Data-Transformer/
  transformer/
    adapters/           # Source adapters (CSV, JSON, API, PDF, DOCX, TXT)
    normalize/          # Per-field normalizers
    pipeline/           # Transform stages (detect, extract, merge, etc.)
    models.py           # Pydantic schemas
    cli.py              # CLI entry point
    web_server.py       # Flask REST API server
    static/             # Static HTML files
  frontend/
    src/
      App.js            # Main React component with Material UI theme
      index.js          # React entry point (Roboto font imports)
      api.js            # Axios client for backend communication
      utils.js          # Title-case utility function
      components/       # Material UI components
        Header.js       # AppBar header
        FileUploader.js # Drag-and-drop file upload
        ConfigSelector.js # Config selector with preview
        ResultsViewer.js # Multi-tab results display (JSON, Cards, Stats)
    public/
      index.html        # Base HTML with Roboto font + Material Icons CDN
    package.json        # React dependencies (Material UI, Axios, react-dropzone)
    .env                # API configuration
  configs/
    default.json        # Default full-schema config
    lean_crm.json       # Lean CRM export config
  data/
    skills_taxonomy.json     # ~150 canonical tech skills + aliases
    merge_policy.json        # Source priority table
    sample_inputs/           # Sample CSV, JSON, TXT files for testing
  tests/
    test_*.py                # Comprehensive test suite (65 tests, 100% passing)
  .gitignore                 # Exclude Python, Node.js, IDE, .claude directory
  DESIGN.md                  # Technical design document
  README.md                  # This file
  run_web_server.py          # Entry point for Flask server
  pyproject.toml
  requirements.txt
```

---

**Candidate Data Transformer - Production-Grade Multi-Source Data Pipeline**
