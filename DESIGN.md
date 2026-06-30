# Multi-Source Candidate Data Transformer - Technical Design

## 1. Pipeline Architecture

The transformation follows a strictly linear, testable pipeline of pure stages:

```
INPUT → DETECT → EXTRACT → NORMALIZE → MERGE → CONFIDENCE → PROJECT → VALIDATE → OUTPUT
```

### Stage Breakdown

**DETECT** (file → adapter)

- Infer source type from: file extension (`.csv`, `.json`, `.pdf`, `.docx`, `.txt`), file path patterns (`github:username`, `linkedin:profile_id`), JSON shape sniffing (check for ATS-specific keys like `candidateName`, `workHistory`).
- If undetectable → default to `unknown_source` adapter, log warning, continue.
- Returns: `(adapter_type: str, raw_input: bytes|dict|str)`.

**EXTRACT** (adapter-specific parsing → RawRecord)

- Each `BaseSourceAdapter` parses input into a normalized intermediate format: `RawRecord`:
  ```python
  RawRecord:
    source_name: str        # "recruiter_csv", "github_profile", etc.
    source_method: str      # "api", "file_parse", "text_regex", etc.
    extracted_fields: dict  # {field_name: (raw_value, extraction_method)}
    raw_text: str | None    # for provenance tracing
    parse_error: str | None # if parsing partially failed
  ```
- **Adapters (one per source type)**:
  1. `RecruiterCSVAdapter` - rows → {name, email, phone, current_company, title}
  2. `ATSJSONAdapter` - JSON {candidateName, contactEmail, phoneNumbers[], employer, jobTitle, skillTags[], workHistory[]} → flattened RawRecord
  3. `GitHubProfileAdapter` - REST API calls (`/users/{username}`, `/users/{username}/repos`) → {name, bio, profile_created_at, repos[]} → infer skills/languages + years_hint
  4. `ResumePDFAdapter` - PDF text extraction + regex heuristics → {name, emails[], phones[], skills[], experience[], education[]}
  5. `ResumeDocxAdapter` - DOCX parsing + regex heuristics → same shape
  6. `LinkedInAdapter` - pre-scraped JSON fixture file (HTML snapshot not supported live; ToS) → {name, headline, experience[], education[]}
  7. `RecruiterNotesAdapter` - free-text regex/heuristics → {mentions: company_names[], job_titles[], skills[], years_experience_hint}

**NORMALIZE** (RawRecord → NormalizedRecord)

- Each field runs through a dedicated, independently testable normalizer:
  - **Phones**: `phonenumbers` library, E.164 format; detect region from other location fields or IP hint, else default to "US" and mark low confidence (0.5). Never invent a country code. Invalid phones → `None`, confidence = 0.3.
  - **Dates**: `YYYY-MM` format. Accept ISO 8601, US M/D/YYYY, "2 years ago" heuristic. Parse ambiguous "Jan 2022" as start-of-month; end dates with no day → last day of month. Unparseable → `None`, log warning.
  - **Country**: ISO-3166 alpha-2 via `pycountry`. Accept common misspellings (fuzzy match with score >0.8), else `None` + low confidence. Map "United States" → "US", etc.
  - **Skills**: Lookup in `skills_taxonomy.json` (curated list ~150 tech skills + aliases, e.g., "ReactJS"/"react"/"React.js" → canonical "React"). Unrecognized skills kept as-is, marked `canonicalized: false`.
  - **Names**: Trim/normalize whitespace. Detect intentional casing (e.g., "van der", "McDonald") via hardcoded rules; preserve. Lowercase only all-caps names (flag as probable acronym). Store original + normalized separately in provenance.
  - **Emails**: lowercase, regex validation (RFC 5322 basic subset), dedup. Invalid → `None`.
  - **Years Experience**: Parse "5 years", "5-7 years", dates-derived hints → numeric float, round to 0.5-year precision. Heuristic-derived (e.g., from resume dates) → confidence 0.6; explicit field → confidence 0.9.

Returns: `NormalizedRecord(candidate_id_temp: str, fields: dict[str, Normalized])` where `Normalized = (value, source, method, success: bool, confidence: 0–1)`.

**MERGE** (RawRecord[] across sources → canonical Candidate)

- **Entity resolution** (match records to same person):
  - Primary match key: normalized email (if present in ≥2 sources).
  - Fallback: `hash(normalized(full_name) + normalized(phone))` if no shared email and both name+phone present; mark `match_method: "fuzzy_name_phone"` for lower certainty downstream.
  - All records of same candidate ID → grouped.
- **Conflict resolution** (per-field, pick best value):
  - **Priority table** (configurable in `merge_policy.json`, but default):
    ```
    Phones, Emails, Location, Links: ATS > Recruiter CSV > Resume > LinkedIn > GitHub > Notes
      (more recent = higher priority within tier)
    Skills, Languages: GitHub > Resume > LinkedIn > ATS > Recruiter CSV > Notes
    Experience, Education: Resume > LinkedIn > ATS > Notes > Recruiter CSV
    Headline: LinkedIn > GitHub > Resume > Notes
    Years Experience: Resume (date-derived) > LinkedIn > ATS > Notes > GitHub (profile age hint)
    ```
  - Numeric aggregation: if sources differ and both high-confidence → weighted average (confidence-weighted).
  - List fields (emails, phones, skills, experience, education): **union + dedupe**, not overwrite. Preserve provenance for each item.
- Returns: canonical `Candidate(full_name, emails[], phones[], location, links, headline, years_experience, skills[], experience[], education[], provenance[], raw_records_merged: [])`.

**CONFIDENCE** (post-merge confidence scoring)

- Per-field score = `sum(corroborating_sources) * source_weight / (total_possible_sources) * normalization_success_factor`.
  - `source_weight`: high-trust (ATS, Resume) = 1.0; mid (LinkedIn, Recruiter CSV) = 0.8; low (Notes) = 0.5; inferred (GitHub) = 0.6.
  - `normalization_success_factor`: 1.0 if no errors, 0.7 if ambiguous/heuristic, 0.4 if fallback, 0.3 if null.
  - Recency bonus: +0.1 if added <6 months ago (rough proxy for "up-to-date").
- `overall_confidence = weighted_avg(field confidences)` where weights are field importance: name/email = 0.3, employment/skills = 0.25, education = 0.15.
- Store in `provenance[]` for each field: `{ field, value, sources: [{source_name, method, confidence}], final_confidence }`.

**PROJECT** (canonical Candidate + runtime config → output shape)

- Config (JSON) specifies:
  - `fields[]`: list of output field definitions
  - Each field: `{ path: "output_key", from: "canonical_path_expr", type, required, normalize?, include_provenance?, include_confidence? }`
  - `from`: dot notation (`full_name`), array indexing (`emails[0]`, `phones[1]`), array flattening (`skills[].name`)
  - `on_missing`: `null` (default) | `omit` | `error`
  - Example:
    ```json
    {
      "fields": [
        {
          "path": "full_name",
          "from": "full_name",
          "type": "string",
          "required": true
        },
        {
          "path": "primary_email",
          "from": "emails[0]",
          "type": "string",
          "required": true
        },
        {
          "path": "phone",
          "from": "phones[0]",
          "type": "string",
          "normalize": "E164"
        },
        {
          "path": "skills",
          "from": "skills[].name",
          "type": "string[]",
          "normalize": "canonical"
        }
      ],
      "include_confidence": true,
      "on_missing": "null"
    }
    ```
- **Path expression engine**: simple recursive descent parser supporting `a.b`, `a[0]`, `a[].b`. No complex boolean logic; keep it minimal.
- Apply per-field `normalize` override if present (e.g., `normalize: "E164"` re-runs phone normalization at projection time, useful for lenient input but strict output).
- Attach `_confidence` and `_provenance` fields if requested (nested under field or as sibling keys per config).
- Returns: `dict` ready for JSON serialization.

**VALIDATE** (output dict → JSON)

- Generate a JSON Schema at runtime from the config (type constraints, required fields).
- Validate projected output against it. On failure: raise descriptive error listing violations.
- Never silently emit invalid JSON.

---

## 2. Canonical Schema (Pydantic)

```python
class Location(BaseModel):
    city: str | None = None
    region: str | None = None
    country: str | None = None  # ISO-3166 alpha-2

class Link(BaseModel):
    type: str  # "linkedin", "github", "portfolio", etc.
    url: str

class Skill(BaseModel):
    name: str                    # canonical or raw
    confidence: float            # 0–1
    canonicalized: bool
    sources: list[str]           # ["github", "resume", ...]

class Experience(BaseModel):
    company: str | None = None
    title: str | None = None
    start: str | None = None     # YYYY-MM
    end: str | None = None       # YYYY-MM
    summary: str | None = None
    source: str                  # "resume", "linkedin", "ats", ...

class Education(BaseModel):
    institution: str | None = None
    degree: str | None = None     # e.g., "Bachelor", "Master"
    field: str | None = None      # "Computer Science"
    end_year: str | None = None   # YYYY
    source: str

class Provenance(BaseModel):
    field: str
    value: str | None
    sources: list[dict]            # [{"source": "recruiter_csv", "method": "column_name", "confidence": 0.9}]
    final_confidence: float
    extraction_method: str         # "api", "regex", "file_parse", "merged", etc.

class Candidate(BaseModel):
    candidate_id: str              # UUID or hash
    full_name: str
    emails: list[str] = []         # lowercase, validated
    phones: list[str] = []         # E.164
    location: Location | None = None
    links: list[Link] = []
    headline: str | None = None
    years_experience: float | None = None
    skills: list[Skill] = []
    experience: list[Experience] = []
    education: list[Education] = []
    provenance: list[Provenance] = []
    overall_confidence: float      # 0–1
```

---

## 3. Normalized Formats

| Field         | Format                 | Library                       | Example                          |
| ------------- | ---------------------- | ----------------------------- | -------------------------------- |
| Phone         | E.164                  | `phonenumbers`                | `+14155552671`                   |
| Date          | YYYY-MM                | `dateutil` + regex            | `2023-05`                        |
| Country       | ISO-3166 alpha-2       | `pycountry`                   | `US`, `GB`, `DE`                 |
| Email         | lowercase, RFC 5322    | `re` + validation             | `john.doe@example.com`           |
| Skills        | canonical names + raw  | custom `skills_taxonomy.json` | canonical="React", raw="ReactJS" |
| Years Exp     | float, 0.5 precision   | `re` + heuristic              | `5.5`, `7.0`                     |
| Name          | title-case (heuristic) | custom rules                  | "John McDonald", "van der Berg"  |
| Location city | title-case             | `re`                          | "San Francisco"                  |

---

## 4. Source Priority & Conflict Resolution

**Default policy** (overridable via config):

| Field Group                                  | Priority (high → low)                                                 | Rationale                                                                        |
| -------------------------------------------- | --------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| Contact (email, phone, location)             | ATS > Recruiter CSV > Resume > LinkedIn > GitHub > Notes              | ATS = employer record; Recruiter CSV = recent sales interaction                  |
| Employment (company, title, start/end dates) | Resume > LinkedIn > ATS > Notes > Recruiter CSV                       | Resume = self-reported official history                                          |
| Skills, Languages                            | GitHub > Resume > LinkedIn > ATS > Recruiter CSV > Notes              | GitHub = demonstrated code + repo topics; Resume = self-reported; others = noisy |
| Headline, Bio                                | LinkedIn > GitHub > Resume > Notes                                    | LinkedIn = curated professional summary                                          |
| Years Experience                             | Resume (date-derived) > LinkedIn > ATS > Notes > GitHub (profile age) | Resume = authoritative if derivable from dates; LinkedIn = explicit self-report  |

**Conflict resolution for scalar fields**:

1. If one source has value and others don't → use that.
2. If multiple sources conflict:
   - Pick by priority table.
   - If tied in priority, pick most recent (modifiedTime/addedDate field if available).
   - If still tied → concatenate with `|` separator in output, mark confidence = 0.4.
3. For numeric fields (years_experience) with conflicting high-confidence sources: weighted average by confidence.

**List fields (emails, phones, skills, experience, education)**:

- Union across all sources.
- Deduplicate: exact string match (case-insensitive for emails; normalized for phones).
- Preserve source/confidence for each item via `sources[]` sub-field.
- Do not drop items even if seen in low-trust sources (e.g., GitHub languages).

---

## 5. Edge Cases & Handling

| #   | Case                                                                    | Handling                                                                                                                                                  | Rationale                                                                |
| --- | ----------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| 1   | Missing/unreadable source file                                          | Log warning, skip that adapter, continue with others. Never crash the pipeline.                                                                           | Robustness constraint; downstream merging handles incomplete data.       |
| 2   | Malformed JSON or corrupted PDF                                         | Caught per-adapter; set `parse_error` in RawRecord; candidate still processed from good sources. Log + add note to provenance.                            | Graceful degradation.                                                    |
| 3   | Same candidate in 3+ sources with conflicting titles/companies          | Resolve via priority table. Log conflict in provenance. Mark `extracted_via: "priority_conflict_resolution"`.                                             | Explainability.                                                          |
| 4   | Phone with no country code, ambiguous region                            | E.164 normalization fails → field becomes `None`, confidence = 0.3. **Never invent** a country code.                                                      | Honesty constraint; downstream can request on_missing="error" if strict. |
| 5   | Candidate in only one low-trust source (Notes only)                     | Still emit candidate with low `overall_confidence` (0.2–0.4). Downstream filters by confidence if needed.                                                 | Complete coverage > false negatives.                                     |
| 6   | Duplicate candidate name+phone match (no shared email)                  | Match via fuzzy_name_phone method. Flag `match_method: "fuzzy_name_phone"` in provenance. Confidence += penalty (e.g., -0.2).                             | Transparency re: match certainty.                                        |
| 7   | Skill name not in taxonomy                                              | Keep raw value, set `canonicalized: false` in Skill model. Include raw + canonical in output.                                                             | Preserve information; don't drop data.                                   |
| 8   | Location field only has country, missing city/region                    | Emit Location with null city/region. Schema allows partial nesting.                                                                                       | Avoid false data.                                                        |
| 9   | Resume with multiple employment entries for same company (role changes) | Keep all entries as separate Experience objects. Tag with `company + title + start + end` as dedup key.                                                   | Preserve career detail; output projection can flatten if needed.         |
| 10  | GitHub profile with no repos or sparse bio                              | Extract name if available, set skills/years_experience to null or heuristic (profile_created_at → years online, not work exp). Mark confidence low (0.4). | Don't confuse platform tenure with career tenure.                        |

**Deliberately descoped** (under time pressure):

- **True fuzzy name matching** (Levenshtein distance) - requires human review for non-obvious duplicates; simpler heuristic (email + exact name) is sufficient for initial release.
- **Multi-language resume parsing** - assume English; non-Latin scripts logged as extraction warnings.
- **Skill synonym learning** - hardcoded taxonomy + aliases only; no ML/embedding clustering.
- **Live LinkedIn scraping** - legal/ToS risk; pre-scraped JSON fixture is workaround.

---

## 6. Runtime Configuration & Projection

**Config file** (`configs/default.json`, `configs/lean_crm.json`):

```json
{
  "version": "1.0",
  "fields": [
    {
      "path": "full_name",
      "from": "full_name",
      "type": "string",
      "required": true,
      "include_provenance": false
    },
    {
      "path": "primary_email",
      "from": "emails[0]",
      "type": "string",
      "required": true,
      "include_confidence": true
    },
    {
      "path": "phone",
      "from": "phones[0]",
      "type": "string",
      "normalize": "E164"
    },
    {
      "path": "skills",
      "from": "skills[].name",
      "type": "string[]",
      "normalize": "canonical"
    },
    {
      "path": "all_experience",
      "from": "experience[]",
      "type": "object[]",
      "include_provenance": true
    }
  ],
  "include_confidence": false,
  "include_provenance": false,
  "on_missing": "null"
}
```

**Projection engine**:

- Parses `from` expression (e.g., `emails[0]`, `skills[].name`, `experience[].{company,title}`).
- Traverses canonical Candidate object to extract value(s).
- Applies type coercion + optional per-field normalization.
- Conditionally includes `_confidence` and `_provenance` fields (sibling keys or nested, per config intent).
- If value missing and `on_missing: "error"` → raise ValueError. Else emit null or omit key.

**Default config** (`configs/default.json`):

- All canonical fields, no projection/renaming. Includes full provenance + confidence.

**Lean CRM config** (`configs/lean_crm.json`):

- Output: `full_name`, `primary_email`, `phone`, `skills` (names only), `years_experience`, `location.country`.
- No provenance, include_confidence at top level only.

---

## 7. Implementation Stages

1. **Models & utilities** (`models.py`, `normalize/`, `utils/`):
   - Pydantic schemas (Candidate, RawRecord, etc.).
   - Normalizer functions (phone, date, country, skill, name, email).
   - `skills_taxonomy.json` with ~150 tech skills + aliases.

2. **Adapters** (`adapters/`):
   - `BaseSourceAdapter` interface.
   - 5 concrete adapters: RecruiterCSV, ATS JSON, GitHub, Resume PDF/DOCX, Notes.
   - `SOURCE_REGISTRY` (dict-based dispatcher).
   - Detector function (file → adapter).

3. **Pipeline stages** (`pipeline/`):
   - `detect()`, `extract()`, `normalize()`, `merge()`, `confidence()`, `project()`, `validate()`.
   - Each stage = pure function or class method, testable in isolation.

4. **CLI** (`cli.py`):
   - `click` with `run` command.
   - Flags: `--sources`, `--config`, `--out`, `--pretty`, `--strict`.

5. **Tests** (`tests/`):
   - Unit tests per normalizer.
   - Integration test (sample inputs → gold output).
   - Edge case tests.

6. **Data** (`data/`):
   - Sample inputs (synthetic 3–4 candidates with conflicts, missing sources).
   - `skills_taxonomy.json`.

---

## 8. Key Assumptions

1. **Email is primary match key** - assumes email addresses are unique per candidate across sources. Fallback to name+phone is explicit "fuzzy" method.
2. **GitHub API available** - public REST API, no auth required for basic queries. Rate limit: 60 req/hr unauthenticated (sufficient for small batches); recommend doc note that users should pass GitHub token for >50 candidates.
3. **LinkedIn pre-scraped only** - accept fixture JSON, not live scraping.
4. **Recruiter CSV has standard columns** - if custom columns, user must manually normalize or map in adapter config (future scope).
5. **Phone numbers are mostly complete** - if incomplete (e.g., local format), normalization fails gracefully. No magic country inference from IP or employer HQ.
6. **Dates parseable with heuristics** - accept ISO 8601, US M/D/YYYY, relative (e.g., "2 years ago"). Ambiguous dates (e.g., "01/02/2020") use US interpretation (M/D/Y).
7. **Output JSON is deterministic** - all lists/dicts are sorted by key; same inputs → byte-identical output.
8. **Config schema is simple** - no conditionals or loops in config; kept to basic path + type + normalization, no transform functions.

---

## 9. Web Server & Frontend Architecture

### Backend (Flask)

The Flask server (`transformer/web_server.py`) exposes the pipeline via REST API:

**Endpoints:**

- `GET /` - Serve frontend HTML
- `POST /api/transform` - Upload files, run pipeline, return JSON results
  - Request: multipart form data with `files[]` (uploaded files) and `config` (JSON string)
  - Response: `{ success, message, data: [candidates], count }`
- `GET /api/configs` - List available projection configs
- `GET /api/schema` - Get default output schema
- `GET /health` - Health check

**Key implementation details:**

- Saves uploaded files to temp directory with proper cleanup
- Runs full pipeline: extract → normalize → merge → confidence → project → validate
- Validates output against config schema before returning
- Logs each stage with counts (debug-friendly)
- CORS enabled for frontend

### Frontend (React + Material UI)

Modern React application (`frontend/`) with Material UI components throughout:

**Architecture:**

- `src/App.js` - Main component with Material UI theme, state management, health check on load
- `src/api.js` - Axios client for backend communication
- `src/utils.js` - Title-case utility for all UI text
- `src/components/`:
  - `Header.js` - AppBar with gradient background
  - `FileUploader.js` - Drag-and-drop file upload with react-dropzone
  - `ConfigSelector.js` - Dropdown selector with live JSON preview
  - `ResultsViewer.js` - Multi-tab results display (JSON, Cards, Statistics)

**Features:**

- ✅ Drag & Drop file upload for multiple files (CSV, JSON, PDF, DOCX, TXT)
- ✅ Config selection with live preview
- ✅ Real-time processing with progress indication
- ✅ Multiple result views: JSON (with syntax highlighting), Cards (expandable), Statistics (counts + avg confidence)
- ✅ Download transformed data as JSON
- ✅ Modern Material UI design with responsive grid layout
- ✅ All UI text uses Title-Case formatting (every first letter capitalized)
- ✅ Backend health check with user-friendly error messages

**Styling:**

- Primary gradient: `#667eea` → `#764ba2`
- Roboto font family (weights 300, 400, 500, 700)
- Material Icons for visual indicators
- Fully responsive (single column on mobile, two columns on desktop)

**Dependencies:**

- React 18+
- Material-UI v5.14+
- Axios for HTTP
- react-dropzone for drag-and-drop
- @emotion/react and @emotion/styled (Material UI's styling engine)

---

## 10. Implementation Patterns & Best Practices

### Pydantic Field Alias Handling

When config JSON uses Python reserved keywords (like `from`), use Field alias with `populate_by_name=True`:

```python
from pydantic import BaseModel, Field, ConfigDict

class FieldConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)  # Allow both alias and field name

    path: str
    from_: str = Field(alias="from")  # Python uses from_, JSON uses "from"
    type: str
    required: bool = False
```

This allows both forms:

- JSON config: `{"from": "canonical_path_expr", ...}`
- Python code: `FieldConfig(from_="canonical_path_expr", ...)`

### Deterministic Serialization

To ensure same inputs produce byte-identical JSON output, exclude fields from serialization:

```python
from datetime import datetime, timezone

class Candidate(BaseModel):
    # ... other fields ...
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), exclude=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), exclude=True)

    def model_dump_json(self, **kwargs) -> str:
        """Override to exclude timestamps from JSON serialization."""
        return super().model_dump_json(**{**kwargs, 'exclude': {'created_at', 'updated_at'}})

    def model_dump(self, **kwargs) -> dict:
        """Override to exclude timestamps from dict serialization."""
        return super().model_dump(**{**kwargs, 'exclude': {'created_at', 'updated_at'}})
```

### Python 3.13+ Deprecation Compatibility

Use `datetime.now(timezone.utc)` instead of deprecated `datetime.utcnow()`:

```python
from datetime import datetime, timezone

# ✅ Correct (Python 3.13+ compatible)
now = datetime.now(timezone.utc)

# ❌ Deprecated (removed in Python 3.13)
now = datetime.utcnow()
```

Applied throughout: `normalize/date.py`, `normalize/years_experience.py`, and all timestamp generation.

### Windows File Handling in Tests

On Windows, `tempfile.NamedTemporaryFile` keeps a file handle open even after context exit (when `delete=False`). Always move file operations outside the context manager:

```python
import tempfile
from pathlib import Path

# ❌ Fails on Windows: file handle still open, can't unlink
with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
    fname = f.name
    f.write("data")
Path(fname).unlink()  # PermissionError on Windows

# ✅ Works on Windows: file handle closed before unlink
with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
    fname = f.name
    f.write("data")
    f.flush()
# Context exits and file handle closes

raw_records = extract([fname])  # Now file is readable

# Clean up after operations complete
Path(fname).unlink(missing_ok=True)
```

---

## 11. Test Results & Validation

**Test Execution:** `pytest tests/ -v`

**Results:**

- **Total Tests:** 65
- **Passed:** 65 (100%)
- **Failed:** 0
- **Deprecation Warnings:** 0

**Coverage:**

- `test_normalizers.py` - 15 tests for phone, email, date, country, name, skills, years_experience normalizers
- `test_adapters.py` - 8 tests for CSV, JSON, DOCX, PDF, TXT, GitHub, LinkedIn adapters
- `test_merge.py` - 12 tests for entity resolution, conflict resolution, fuzzy matching
- `test_projection.py` - 10 tests for path expressions, config validation, type coercion
- `test_integration.py` - 12 tests for full pipeline with sample data
- `test_edge_cases.py` - 8 tests for malformed data, missing fields, empty files

**Key validation checks:**

- ✅ Normalizers preserve data integrity (raw value stored in provenance)
- ✅ Merge correctly handles email-primary and fuzzy name+phone matching
- ✅ Conflict resolution follows priority table (validated against merge_policy.json)
- ✅ Path expressions support dotted notation, array indexing, and flattening
- ✅ Timestamps excluded from JSON (determinism test passes)
- ✅ All deprecation warnings eliminated (datetime.now(timezone.utc) throughout)
- ✅ Windows file handling compatible (temp file cleanup works correctly)

---

**Candidate Data Transformer - Complete Implementation**
