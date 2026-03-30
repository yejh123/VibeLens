# Upload and Donation — Specification

Two features that move session data in and out of VibeLens. Upload lets users bring external agent sessions into the platform. Donation lets users contribute sessions for academic research.

Upload is demo-mode only (the Upload button is hidden in self-use mode). Donation works in both modes: sessions are always packaged into a ZIP and sent to the configured `donation_url`.

**Files:**

- `src/vibelens/services/upload/processor.py` — Upload orchestration
- `src/vibelens/services/upload/visibility.py` — Token-based visibility filtering
- `src/vibelens/services/session/donation.py` — Donation orchestration: visibility check, delegate to sender
- `src/vibelens/services/donation/sender.py` — Donation sending: collect files from any store, create ZIP, POST to server
- `src/vibelens/services/donation/receiver.py` — Donation receiving (demo mode): stream ZIP, index manifest
- `src/vibelens/services/session/crud.py` — Session retrieval and export (no donation logic)
- `src/vibelens/api/upload.py` — Upload HTTP endpoints
- `src/vibelens/api/donation.py` — Donation HTTP endpoints (donate + receive)
- `src/vibelens/utils/zip.py` — ZIP validation and safe extraction
- `src/vibelens/storage/conversation/disk.py` — DiskStore (save, copy_to_dir, rglob index)
- `src/vibelens/storage/conversation/base.py` — TrajectoryStore (get_session_source)
- `src/vibelens/storage/conversation/local.py` — LocalStore (get_data_dir)
- `src/vibelens/ingest/parsers/base.py` — BaseParser (get_session_files)
- `src/vibelens/ingest/parsers/claude_code.py` — ClaudeCodeParser (get_session_files override for sub-agents)
- `frontend/src/components/upload-dialog.tsx` — Upload UI
- `frontend/src/components/donate-consent-dialog.tsx` — Donation consent UI
- `frontend/src/app.tsx` — Toolbar buttons, dialog state, session token

## Architecture Overview

```
                         Frontend (React)
                              │
               ┌──────────────┼──────────────┐
               │              │              │
          Upload Dialog   Donate Button   Session Token
               │              │         (ephemeral UUID)
               │              │              │
               ▼              ▼              │
          POST /upload/zip  POST /sessions/donate
               │              │              │
               │              ▼              │
               │    donation.donate_sessions()
               │         │                   │
               │         ▼                   │
               │    sender.send_donation()   │
               │    (any store type)         │
               │         │                   │
               │    ┌────┴────────┐          │
               │    │             │          │
               │    ▼             ▼          │
               │  collect from  collect from │
               │  LocalStore    DiskStore    │
               │  (raw JSONL)   (parsed JSON)│
               │    │             │          │
               │    └─────┬───────┘          │
               │          ▼                  │
               │    ZIP creation             │
               │    + POST to                ▼
               │    /api/donation/receive  X-Session-Token header
               │         │                (sent on all requests)
               ▼         ▼
        processor.    receiver.
        process_zip() receive_donation()
               │         │
    ┌──────────┼────┐    │
    │          │    │    │
    ▼          ▼    ▼    ▼
receive_   extract  parse {donation_dir}/
  zip      +discover +store {upload_id}.zip
    │          │    │    index.jsonl
    ▼          ▼    ▼
 {upload_dir}/{upload_id}/
   {upload_id}.zip
   {session_id}.json
   _index.jsonl
```

## Storage Layout

### Upload Storage

Everything lives under `settings.upload_dir` (default `~/.vibelens/uploads/`).

```
~/.vibelens/uploads/                          ← settings.upload_dir (DiskStore root)
├── metadata.jsonl                            ← Global upload manifest (append-only)
├── _index.jsonl                              ← Demo example sessions index
├── {demo_session_id}.json                    ← Demo example trajectory
├── 20260329143012_a1b2/                      ← Upload #1 subdirectory
│   ├── 20260329143012_a1b2.zip               ← Original zip (permanent archive)
│   ├── _index.jsonl                          ← Upload session index (tagged with _upload_id)
│   ├── {session_id_A}.json                   ← Parsed trajectory
│   └── {session_id_B}.json
└── 20260329150045_c3d4/                      ← Upload #2 subdirectory
    ├── 20260329150045_c3d4.zip
    ├── _index.jsonl
    └── {session_id_C}.json
```

The main DiskStore discovers all `_index.jsonl` files via `rglob("_index.jsonl")`, so upload subdirectory sessions appear automatically.

### Donation Storage (Receiver)

Received donations live under `settings.donation_dir` (default `~/.vibelens/donations/`).

```
~/.vibelens/donations/                        ← settings.donation_dir
├── index.jsonl                               ← Append-only donation index
├── 20260329143012_a1b2.zip                   ← Donation #1 (raw + parsed + manifest)
└── 20260329150045_c3d4.zip                   ← Donation #2
```

Each ZIP contains a wrapping directory named by `donation_id`:
```
{donation_id}.zip
└── {donation_id}/
    ├── manifest.json                         ← Session metadata (IDs, agent types, counts)
    ├── raw/
    │   ├── claude_code/                      ← LocalStore sessions (raw JSONL)
    │   │   └── projects/.../uuid.jsonl
    │   │   └── projects/.../uuid/subagents/
    │   │       └── agent-*.jsonl
    │   └── 20260329143012_a1b2.zip           ← Uploaded sessions (original upload ZIP)
    └── parsed/
        └── {session_id}.json                 ← Parsed trajectory group JSON array
```

For uploaded sessions (DiskStore with `_upload_id` tag), `raw/` contains the original upload ZIP instead of the parsed JSON duplicate. Multiple sessions from the same upload share a single ZIP entry (deduplicated).

## Upload Feature

### Upload ID Format

```
{YYYYMMDDHHMMSS}_{4-char-hex-uuid}
         │                │
  UTC timestamp     uuid4().hex[:4]

Example: 20260329143012_a1b2
```

Generated by `generate_upload_id()` using `datetime.now(UTC)` and `uuid4().hex[:SHORT_UUID_LENGTH]`.

### API Endpoints

**GET /upload/commands**

Returns a platform-specific CLI command the user runs to zip their agent data.

```
Request:  ?agent_type=claude_code&os_platform=macos
Response: {"command": "cd ~/.claude && zip -r ...", "description": "Output: ~/.claude/claude-data.zip"}
```

Supported agents: `claude_code`, `codex`, `gemini`.
Supported platforms: `macos`, `linux`, `windows`.

**POST /upload/zip**

Accepts a multipart form upload with the zip file.

```
Form fields:
  file        — .zip file (required)
  agent_type  — "claude_code" | "codex" | "gemini" (required)

Headers:
  X-Session-Token — Browser tab UUID for ownership (optional)

Response: UploadResult
  {
    "files_received": 1,
    "sessions_parsed": 12,
    "steps_stored": 847,
    "skipped": 2,
    "errors": [{"filename": "broken.jsonl", "error": "Invalid JSON at line 3"}]
  }
```

### Upload Pipeline

```
process_zip(file, agent_type, session_token)
    │
    ├─ 1. receive_zip()
    │      Stream file to {upload_dir}/{upload_id}/{upload_id}.zip
    │      ├─ Read in 64 KB chunks (settings.stream_chunk_size)
    │      ├─ Track total bytes written
    │      └─ Abort if total > settings.max_zip_bytes (10 GB)
    │
    ├─ 2. extract_and_discover()
    │      │
    │      ├─ validate_zip()
    │      │   ├─ Check file size on disk
    │      │   ├─ Verify zipfile.is_zipfile()
    │      │   └─ _check_zip_entries()
    │      │       ├─ Reject path traversal: ".." or leading "/"
    │      │       ├─ Reject symlinks: Unix mode bits in external_attr
    │      │       ├─ Filter by ALLOWED_EXTENSIONS (.json, .jsonl, .project_root, .txt)
    │      │       ├─ Accumulate uncompressed size (max 20 GB)
    │      │       └─ Count files (max 10,000)
    │      │
    │      ├─ extract_zip()
    │      │   Extract only allowed-extension files to {upload_id}/_extracted/
    │      │
    │      └─ discover_session_files()
    │          Use agent-specific discovery to find parseable session files
    │
    ├─ 3. _parse_and_store_files()
    │      │
    │      ├─ Create DiskStore at {upload_dir}/{upload_id}/
    │      │   with default_tags = {"_upload_id": upload_id}
    │      │
    │      ├─ get_parser(agent_type) → parser instance
    │      │
    │      └─ For each session file:
    │          ├─ parser.parse_file() → list[Trajectory]
    │          ├─ store.save(trajectories)
    │          │   ├─ Write {session_id}.json (full trajectory data)
    │          │   └─ Append summary + _upload_id tag to _index.jsonl
    │          └─ Accumulate: sessions_parsed, steps_stored, skipped, errors
    │
    ├─ 4. append_upload_metadata()
    │      Append JSON line to {upload_dir}/metadata.jsonl
    │
    ├─ 5. register_upload(session_token, upload_id)
    │      Map token → upload_id in visibility module
    │
    ├─ 6. Invalidate caches
    │      ├─ main_store.invalidate_index()  ← rglob rediscovers upload subdir
    │      ├─ invalidate_search_index()
    │      └─ invalidate_dashboard_cache()
    │
    └─ finally: cleanup_extraction()
           Remove {upload_id}/_extracted/ (keep zip as archive)
```

### ZIP Security

```
validate_zip(zip_path)
    │
    ├─ Size check: stat().st_size ≤ max_zip_bytes
    │
    ├─ Format check: zipfile.is_zipfile()
    │
    └─ Entry scan: _check_zip_entries()
        │
        For each ZipInfo entry:
        │
        ├─ Path traversal?
        │   ".." in filename OR filename.startswith("/")
        │   → ValueError("Path traversal detected")
        │
        ├─ Symlink?
        │   (external_attr >> 16) & 0o170000 == 0o120000
        │   → ValueError("Symlink detected")
        │
        ├─ Allowed extension?
        │   suffix ∈ {.json, .jsonl, .project_root, .txt}
        │   → Skip if not allowed (silently ignored)
        │
        ├─ Size budget:
        │   sum(file_size) ≤ max_extracted_bytes (20 GB)
        │
        └─ File count:
            count ≤ max_file_count (10,000)
```

### Upload Metadata (metadata.jsonl)

Single append-only JSONL file at `{upload_dir}/metadata.jsonl`. One JSON object per upload.

```json
{
  "upload_id": "20260329143012_a1b2",
  "timestamp": "2026-03-29T14:30:12.345678+00:00",
  "agent_type": "claude_code",
  "original_filename": "claude-data.zip",
  "sessions": [
    {
      "session_id": "f733d455-933d-4655-b344-356f03b3bcc5",
      "trajectory_count": 3,
      "step_count": 142,
      "source_file": "f733d455-933d-4655-b344-356f03b3bcc5.jsonl"
    }
  ],
  "totals": {
    "sessions_parsed": 12,
    "steps_stored": 847,
    "skipped": 2,
    "errors": 1
  }
}
```

### DiskStore Index Discovery

The main DiskStore (rooted at `settings.upload_dir`) discovers uploaded sessions via recursive glob:

```
DiskStore._build_index()
    │
    └─ rglob("_index.jsonl")
        │
        ├─ {upload_dir}/_index.jsonl                    ← demo examples
        ├─ {upload_dir}/20260329143012_a1b2/_index.jsonl ← upload #1
        └─ {upload_dir}/20260329150045_c3d4/_index.jsonl ← upload #2

        For each _index.jsonl:
            For each line (JSON summary):
                ├─ _metadata_cache[session_id] = summary
                └─ _index[session_id] = (parent_dir/{session_id}.json, parser)
```

Uploaded sessions are distinguished by the `_upload_id` key in their summary. The visibility layer uses this tag to filter what each browser tab can see.

## Visibility Filtering

Upload sessions are isolated per browser tab using ephemeral session tokens.

```
Browser Tab A                   Browser Tab B
     │                               │
     │ X-Session-Token: "uuid-A"     │ X-Session-Token: "uuid-B"
     │                               │
     ▼                               ▼
┌─────────────────────────────────────────┐
│        visibility._token_uploads        │
│                                         │
│  "uuid-A" → {"20260329143012_a1b2"}     │
│  "uuid-B" → {"20260329150045_c3d4"}     │
└─────────────────────────────────────────┘
         │                    │
         ▼                    ▼
   Tab A sees:           Tab B sees:
   - All root sessions   - All root sessions
   - Upload a1b2 only    - Upload c3d4 only
```

### Token Lifecycle

```
Page load → crypto.randomUUID() → sessionToken state
    │
    ├─ Never persisted (new token on each page load)
    ├─ Sent as X-Session-Token header on every fetch()
    └─ Server stores token → upload_id mapping in memory
       (cleared on server restart)
```

### Filtering Functions

**filter_visible(summaries, session_token)**

```
For each summary in summaries:
    │
    ├─ No _upload_id? → Always visible (root/demo session)
    │
    └─ Has _upload_id?
        ├─ Token owns that upload_id? → Visible
        └─ Otherwise → Hidden
```

**is_session_visible(meta, session_token)**

Same logic for a single session, used by `get_session()` and `donate_sessions()` to gate access.

## Donation Feature

All donations follow the same path regardless of app mode: sessions are packaged into a ZIP and sent to the configured `donation_url` via HTTP POST. The sender works with any store type — `LocalStore` provides raw JSONL files (including sub-agents), while `DiskStore` provides parsed JSON files.

### Orchestration

```
donation.donate_sessions(session_ids, session_token)
    │
    ├─ _filter_visible_ids()               ← visibility gate
    │   └─ is_session_visible() per session
    │
    └─ sender.send_donation(visible_ids)
        ├─ _collect_sessions()             ← gather files from any store
        ├─ _create_donation_zip()          ← package into ZIP
        └─ _send_zip()                     ← POST to donation server
```

### Sender Pipeline

```
sender.send_donation(session_ids, session_token)
    │
    ├─ 1. _collect_sessions(store, session_ids)
    │      For each session_id:
    │      │
    │      ├─ store.get_session_source(session_id)
    │      │   → (filepath, parser) from _index
    │      │
    │      ├─ store.get_metadata(session_id)
    │      │   → check for _upload_id tag (uploaded sessions)
    │      │
    │      ├─ _resolve_raw_files(store, filepath, parser, source_upload_id)
    │      │   ├─ If source_upload_id set:
    │      │   │   ├─ _locate_upload_zip(upload_id)
    │      │   │   │   → {upload_dir}/{upload_id}/{upload_id}.zip
    │      │   │   └─ Return [(zip_path, "raw/{upload_id}.zip")]
    │      │   │
    │      │   ├─ Fallback (no upload or ZIP missing):
    │      │   │   ├─ parser.get_session_files(filepath)
    │      │   │   │   ├─ BaseParser default: [session_file]
    │      │   │   │   └─ ClaudeCodeParser: + subagents/agent-*.jsonl
    │      │   │   │
    │      │   │   ├─ LocalStore: store.get_data_dir(parser) or parser.LOCAL_DATA_DIR
    │      │   │   │   → data_dir for computing relative paths
    │      │   │   ├─ DiskStore: data_dir = None
    │      │   │   │   → uses filename only (no local agent dir)
    │      │   │   │
    │      │   │   └─ For each file:
    │      │   │       rel = file.relative_to(data_dir) or file.name
    │      │   │       zip_path = "raw/{agent_type}/{rel}"
    │      │
    │      └─ store.load(session_id)
    │          → parsed trajectory JSON
    │
    ├─ 2. generate_upload_id() → donation_id
    │
    ├─ 3. _create_donation_zip(sessions_data, donation_id)
    │      Create temp ZIP with wrapping directory:
    │      ├─ {donation_id}/raw/{...}             ← raw files (deduplicated)
    │      ├─ {donation_id}/parsed/{session_id}.json
    │      └─ {donation_id}/manifest.json
    │
    ├─ 4. _send_zip(zip_path, url, donation_id)
    │      POST as "{donation_id}.zip" to {donation_url}/api/donation/receive
    │      via httpx.AsyncClient (120s timeout)
    │
    └─ finally: delete temp ZIP
```

### Manifest Format (manifest.json inside ZIP)

```json
{
  "donation_id": "20260330120000_abcd",
  "timestamp": "2026-03-30T15:30:45+00:00",
  "vibelens_version": "0.9.12",
  "sessions": [
    {
      "session_id": "uuid-1",
      "agent_type": "claude_code",
      "trajectory_count": 3,
      "step_count": 142,
      "raw_files": [
        "20260330120000_abcd/raw/claude_code/projects/.../uuid.jsonl",
        "20260330120000_abcd/raw/claude_code/projects/.../uuid/subagents/agent-abc123.jsonl"
      ]
    },
    {
      "session_id": "uuid-2",
      "agent_type": "claude_code",
      "source_upload_id": "20260329143012_a1b2",
      "trajectory_count": 1,
      "step_count": 42,
      "raw_files": ["20260330120000_abcd/raw/20260329143012_a1b2.zip"]
    }
  ]
}
```

- `donation_id`: Wrapping directory name, used by the receiver for filename
- `source_upload_id`: Present only for uploaded sessions — points to the original upload ZIP in `raw/`
- `raw_files` paths include the `{donation_id}/` prefix

### Demo Mode: Receiver Pipeline

```
receiver.receive_donation(file: UploadFile)
    │
    ├─ 1. generate_upload_id() → temp_id
    │
    ├─ 2. _stream_to_disk(file, _tmp_{temp_id}.zip, max_bytes)
    │      Stream ZIP to temp path in donation_dir
    │      ├─ Read in 64 KB chunks
    │      └─ Abort if total > settings.max_zip_bytes
    │
    ├─ 3. _read_manifest(temp_path)
    │      ├─ _find_manifest_in_zip(names)
    │      │   ├─ Check root: "manifest.json" (legacy)
    │      │   └─ Check one-level deep: "{dir}/manifest.json" (new format)
    │      ├─ BadZipFile → HTTP 400 + delete corrupt file
    │      └─ Missing/invalid manifest → empty dict (graceful degradation)
    │
    ├─ 4. Extract donation_id from manifest (or generate fallback)
    │      Rename temp file → {donation_id}.zip
    │
    └─ 5. _append_to_index(donation_dir, entry)
           Append JSON line to {donation_dir}/index.jsonl
           Index entry uses "donation_id" field (not "upload_id")
```

### Donation Index (index.jsonl)

Append-only JSONL at `{donation_dir}/index.jsonl`. One entry per received donation.

```json
{
  "donation_id": "20260330120000_abcd",
  "timestamp": "2026-03-30T15:30:45+00:00",
  "zip_filename": "20260330120000_abcd.zip",
  "zip_size_bytes": 1234567,
  "vibelens_version": "0.9.12",
  "sessions": [
    {
      "session_id": "uuid-1",
      "agent_type": "claude_code",
      "trajectory_count": 3,
      "step_count": 142,
      "raw_files": ["20260330120000_abcd/raw/claude_code/projects/.../uuid.jsonl"]
    },
    {
      "session_id": "uuid-2",
      "agent_type": "claude_code",
      "source_upload_id": "20260329143012_a1b2",
      "trajectory_count": 1,
      "step_count": 42,
      "raw_files": ["20260330120000_abcd/raw/20260329143012_a1b2.zip"]
    }
  ]
}
```

### API Endpoints

All donation endpoints live in `src/vibelens/api/donation.py`.

**POST /sessions/donate**

Initiate a donation from the frontend. Always sends to the configured `donation_url`.

```
Request:
  {"session_ids": ["uuid-1", "uuid-2", "uuid-3"]}

Headers:
  X-Session-Token: "browser-tab-uuid"

Response: DonateResult
  {"total": 3, "donated": 2, "errors": [{"session_id": "uuid-3", "error": "Session not found"}]}
```

**POST /api/donation/receive**

Server-to-server endpoint. Receives a donation ZIP from a self-use instance.

```
Request:
  multipart/form-data with "file" field containing the donation ZIP

Response:
  {"donation_id": "20260330120000_abcd", "session_count": 3, "zip_size_bytes": 1234567}
```

### Parser: get_session_files()

`BaseParser.get_session_files(session_file)` returns all files belonging to a session. Used by the donation sender to collect raw files for the ZIP.

```
BaseParser (default):
    → [session_file]                          ← single file

ClaudeCodeParser (override):
    → [session_file]                          ← main JSONL
    + sorted(subagent_dir.glob("agent-*.jsonl"))
      where subagent_dir = session_file.parent / session_file.stem / "subagents"
```

Other parsers (Codex, Gemini, OpenClaw) use the default — single-file sessions.

### Store: Session Source Access

Two new methods expose internal index data needed by the donation sender:

**TrajectoryStore.get_session_source(session_id)**

Returns `(filepath, parser)` tuple from `_index`, or `None`. Gives the sender the original file path and parser instance.

**LocalStore.get_data_dir(parser)**

Returns the resolved data directory for a parser from `_data_dirs`, or `None`. Used to compute relative paths inside the donation ZIP (e.g. `projects/.../uuid.jsonl` relative to `~/.claude`).

### User Flow

```
User checks sessions    →  Clicks "Donate"  →  Consent dialog
in sidebar checkboxes        (rose button)         │
                                                   │ User reads 4 consent items
                                                   │ Checks "I agree" box
                                                   │ Clicks "Donate"
                                                   ▼
                                           POST /sessions/donate
                                           {session_ids: [...]}
                                                   │
                                                   ▼
                                           ZIP creation + POST
                                           to donation_url
                                                   │
                                                   ▼
                                            DonateResult
```

### Dialog State Machine

```
            ┌──────────────┐
            │   hidden     │ ← initial state
            └──────┬───────┘
                   │ user clicks Donate button
                   ▼
            ┌─────────────────┐
            │ donate-confirm  │ → DonateConsentDialog
            └──────┬──────────┘
                   │ user agrees + clicks Donate
                   ▼
            ┌─────────────────┐
            │   donating      │ → ConfirmDialog (loading spinner)
            └──────┬──────────┘
                   │ server responds
                   ▼
            ┌─────────────────┐
            │ donate-result   │ → ConfirmDialog (success/error summary)
            └──────┬──────────┘
                   │ user clicks OK
                   │ if donated > 0: clear checked sessions
                   ▼
            ┌─────────────────┐
            │    hidden       │
            └─────────────────┘
```

### Consent Items

The donation dialog requires explicit agreement to four statements:

1. Sessions may contain code snippets, file paths, and conversation content
2. Data will be used for academic research by CHATS-Lab at Northeastern University
3. User has reviewed sessions and confirmed no sensitive credentials or API keys
4. Data may be shared in anonymized or aggregated form in research publications

The "Donate" button is disabled until the checkbox is checked.

## Frontend Integration

### Upload Button (demo mode only)

```
Toolbar (sidebar)
┌────────────┬────────────┬────────────┐
│  Upload    │  Download  │   Donate   │   ← demo mode: 3 columns
│  (violet)  │ (emerald)  │   (rose)   │
└────────────┴────────────┴────────────┘

┌─────────────────┬─────────────────────┐
│    Download     │      Donate         │   ← self-use mode: 2 columns
│   (emerald)     │      (rose)         │      Upload button hidden
└─────────────────┴─────────────────────┘
```

The Upload button renders only when `appMode === "demo"`. The grid layout adapts: 3 columns in demo mode, 2 in self-use mode.

### Upload Dialog Steps

```
Step 1: Select                    Step 2: Upload
┌──────────────────────┐         ┌────────────────────────┐
│ Agent Type           │         │ Run this command:      │
│ [Claude] [Codex]     │         │ ┌───────────────────┐  │
│ [Gemini]             │         │ │ cd ~/.claude &&.. │  │
│                      │         │ └───────────────────┘  │
│ Operating System     │         │                        │
│ [macOS] [Linux]      │         │ Drop .zip file here    │
│ [Windows]            │  Next   │ ┌──────────────────┐  │
│                      │ ────►   │ │                  │  │
│        [Next]        │         │ │  Drop zone       │  │
└──────────────────────┘         │ │                  │  │
                                 │ └──────────────────┘  │
                                 │                       │
                                 │ [████████░░] 67%      │
                                 │ Sending 24.5 MB       │
                                 │                       │
                                 │ Sessions: 12          │
                                 │ Steps: 847            │
                                 │          [Done]       │
                                 └───────────────────────┘
```

Upload uses `XMLHttpRequest` (not fetch) for progress tracking. Two phases:

1. **Sending**: Deterministic progress bar (0-100%) tracking bytes sent
2. **Processing**: Pulsing indeterminate bar while server parses

## Configuration Reference

| Setting | Default | Description |
|---------|---------|-------------|
| `upload_dir` | `~/.vibelens/uploads` | Base directory for uploads, parsed data, and metadata |
| `donation_url` | `https://vibelens.chats-lab.org` | URL of the donation server (sender target in all modes) |
| `donation_dir` | `~/.vibelens/donations` | Directory for received donation ZIPs and index (demo mode) |
| `max_zip_bytes` | 10 GB | Maximum zip file size (shared by upload and donation) |
| `max_extracted_bytes` | 20 GB | Maximum total uncompressed size |
| `max_file_count` | 10,000 | Maximum files in archive |
| `stream_chunk_size` | 64 KB | Chunk size for streaming uploads to disk |

All configurable via environment variables with `VIBELENS_` prefix (e.g. `VIBELENS_DONATION_URL`), `.env` file, or YAML config.

YAML config sections:
```yaml
# config/self-use.yaml
donation:
  url: https://vibelens.chats-lab.org

# config/demo.yaml
donation:
  dir: ~/.vibelens/donations
```

## Constants Reference

| Constant | Value | Location |
|----------|-------|----------|
| `UPLOAD_ID_TIME_FORMAT` | `"%Y%m%d%H%M%S"` | processor.py |
| `SHORT_UUID_LENGTH` | `4` | processor.py |
| `EXTRACTED_SUBDIR` | `"_extracted"` | processor.py |
| `METADATA_FILENAME` | `"metadata.jsonl"` | processor.py |
| `INDEX_FILENAME` | `"_index.jsonl"` | disk.py |
| `DONATION_RECEIVE_PATH` | `"/api/donation/receive"` | sender.py |
| `MANIFEST_FILENAME` | `"manifest.json"` | sender.py, receiver.py |
| `HTTP_TIMEOUT_SECONDS` | `120` | sender.py |
| `INDEX_FILENAME` | `"index.jsonl"` | receiver.py |
| `ALLOWED_EXTENSIONS` | `{.json, .jsonl, .project_root, .txt}` | zip.py |
| `UNIX_FILE_TYPE_MASK` | `0o170000` | zip.py |
| `UNIX_SYMLINK_TYPE` | `0o120000` | zip.py |

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Non-DiskStore (self-use mode) | Upload: HTTP 400 "Uploads not supported in self-use mode" |
| File not `.zip` | HTTP 400 "Only .zip files are accepted" |
| Unknown agent_type | HTTP 400 "Unknown agent_type: ..." |
| Zip exceeds size limit during streaming | HTTP 400 "File exceeds N MB limit", partial file deleted |
| Donation ZIP exceeds size limit | HTTP 400 "Donation ZIP exceeds N MB limit", partial file deleted |
| Invalid donation ZIP (BadZipFile) | HTTP 400 "Invalid ZIP file", corrupt file deleted |
| Missing/invalid manifest in donation ZIP | Graceful degradation: empty session list in index |
| Path traversal in upload zip | ValueError during validation |
| Symlink in upload zip | ValueError during validation |
| Single file parse failure | Logged, added to errors list, other files continue |
| Session not visible for donation | Error "Session not found" in per-session errors |
| Source file not found in index | Error "Source file not found" in per-session errors |
| Session load failure | Error "Failed to load session" in per-session errors |
| httpx HTTP error during send | Error "Upload failed: ..." in errors, `donated: 0` |
| Extraction dir cleanup failure | `ignore_errors=True` (best-effort) |

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `httpx` | `>=0.27.0` | Async HTTP client for donation sender (POST ZIP to server) |
| `fastapi` | `>=0.115.0` | API framework (UploadFile for receiver endpoint) |
