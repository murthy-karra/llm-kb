# 001 — Wiki File Upload with S3 + GuardDuty Scanning

## Overview

Admin users can create multiple wikis. Each wiki holds uploaded files (single, multi, folder, nested folders). Files upload to S3 quarantine via presigned URLs, get scanned by GuardDuty Malware Protection, then transfer to the wiki bucket once clean. The frontend shows real-time upload + scan progress with a batch-aware upload manager.

## Constraints

- Presigned URLs: 15 min expiry, 10 MB max per file
- Allowed types: PDF, DOCX, PPTX, MD, TXT
- Upload concurrency: 4 simultaneous uploads per batch
- Scan polling: backend polls S3 tags every 10s, 5 min max timeout
- Frontend polls backend every 5s for scan status updates
- S3 key format: `wikis/{wiki_id}/{relative_path}/{filename}`
- AWS profile: `personal` (via `LLMKB_AWS_PROFILE`)
- Buckets: `llm-kb-wiki-quarantine` (upload target), `llm-kb-wiki` (clean storage)

## File States

```
rejected       → client-side validation failed (size/type) — never uploaded
queued         → validated, waiting for upload slot
uploading      → presigned URL obtained, PUT in progress (0-100%)
pending_scan   → uploaded to quarantine, waiting for GuardDuty tag
clean          → GuardDuty tagged NO_THREATS_FOUND, transferred to wiki bucket
failed_scan    → GuardDuty tagged THREATS_FOUND (malware detected)
failed_timeout → 5 min scan timeout exceeded
failed_upload  → S3 PUT failed
```

---

## Phase 1: Database Models & Migration

### Step 1.1 — Create Wiki model

**File:** `backend/app/models/wiki.py`

```python
class Wiki:
    __tablename__ = "wikis"
    __table_args__ = {"schema": "app"}

    id: str              # UUID PK
    name: str            # Wiki display name
    description: str     # Optional description
    created_by: str      # FK → auth.users.id
    created_at: datetime
    updated_at: datetime
```

**Definition of Done:**
- [ ] `Wiki` model defined with `Mapped`/`mapped_column` (match `User` model style)
- [ ] Relationship to `User` model via `created_by` FK
- [ ] Model importable: `from app.models.wiki import Wiki`

### Step 1.2 — Create WikiFile model

**File:** `backend/app/models/wiki_file.py`

```python
class WikiFile:
    __tablename__ = "wiki_files"
    __table_args__ = {"schema": "app"}

    id: str                # UUID PK
    wiki_id: str           # FK → app.wikis.id
    filename: str          # Original filename (e.g. "handbook.pdf")
    relative_path: str     # Folder path within upload (e.g. "policies/2024/")
    s3_key: str            # Full S3 key
    content_type: str      # MIME type
    size_bytes: int        # File size
    status: str            # One of: pending_scan, clean, failed_scan, failed_timeout, failed_upload
    scan_started_at: datetime | None
    transferred_at: datetime | None
    uploaded_by: str       # FK → auth.users.id
    created_at: datetime
```

**Definition of Done:**
- [ ] `WikiFile` model defined with status as a string column (not enum — easier to extend)
- [ ] FKs to `Wiki` and `User`
- [ ] Index on `(wiki_id, status)` for efficient scan polling queries
- [ ] Model importable: `from app.models.wiki_file import WikiFile`

### Step 1.3 — Export models and write migration

**File:** `backend/app/models/__init__.py` — export `Wiki`, `WikiFile`
**File:** `backend/migrations/002_create_wiki_schema_and_tables.sql`

```sql
CREATE SCHEMA IF NOT EXISTS app;

CREATE TABLE app.wikis ( ... );
CREATE TABLE app.wiki_files ( ... );
CREATE INDEX idx_wiki_files_wiki_status ON app.wiki_files(wiki_id, status);
```

**Definition of Done:**
- [ ] `__init__.py` exports both models
- [ ] SQL migration creates `app` schema, both tables, indexes, FK constraints
- [ ] `init_db()` in `database.py` creates the `app` schema alongside `auth`
- [ ] Server starts cleanly, tables are created

---

## Phase 2: Backend API — Wiki CRUD

### Step 2.1 — Wiki CRUD endpoints

**File:** `backend/app/api/wikis.py` (new APIRouter)
**Register in:** `backend/app/main.py`

Endpoints:

```
POST   /api/wikis                → Create wiki (admin only)
GET    /api/wikis                → List wikis for current user
GET    /api/wikis/{wiki_id}      → Get wiki detail + file counts
PUT    /api/wikis/{wiki_id}      → Update wiki name/description (admin only)
DELETE /api/wikis/{wiki_id}      → Delete wiki + all files (admin only)
```

Request/response schemas (Pydantic models in same file or `schemas.py`):

```python
class CreateWikiRequest(BaseModel):
    name: str           # max 100 chars
    description: str = ""

class WikiResponse(BaseModel):
    id: str
    name: str
    description: str
    file_count: int
    total_size_bytes: int
    created_by: str
    created_at: datetime
```

**Definition of Done:**
- [ ] All 5 endpoints implemented with `Depends(get_current_user)` auth
- [ ] Create/Update/Delete restricted to `role == "admin"`
- [ ] List returns wikis with aggregate file_count and total_size_bytes
- [ ] Router registered in `main.py` with prefix `/api/wikis`
- [ ] Manual test: create a wiki via curl, list it, update it, delete it

---

## Phase 3: Backend API — Presigned Upload + Scan Polling

### Step 3.1 — Presigned URL generation endpoint

**File:** `backend/app/api/uploads.py` (new APIRouter)

```
POST /api/wikis/{wiki_id}/uploads/presign
```

Request body — batch of files:
```python
class PresignFileRequest(BaseModel):
    filename: str
    relative_path: str = ""   # folder path from upload root
    size_bytes: int
    content_type: str

class PresignBatchRequest(BaseModel):
    files: list[PresignFileRequest]
```

Response — per-file result (accepted or rejected):
```python
class PresignedFileResponse(BaseModel):
    filename: str
    relative_path: str
    presigned_url: str | None    # None if rejected
    s3_key: str | None
    file_id: str | None          # WikiFile.id for tracking
    rejected: bool = False
    reject_reason: str | None = None

class PresignBatchResponse(BaseModel):
    accepted: list[PresignedFileResponse]
    rejected: list[PresignedFileResponse]
```

Logic:
1. Validate wiki exists, user has access
2. For each file in batch:
   - Reject if `size_bytes > 10MB`
   - Reject if `content_type` not in allowed list (pdf, docx, pptx, md, txt)
   - Reject if filename contains path traversal chars
3. For accepted files:
   - Generate S3 key: `wikis/{wiki_id}/{relative_path}/{filename}`
   - Create `WikiFile` record with `status = "pending_scan"`
   - Generate presigned PUT URL with conditions: `Content-Length <= 10MB`, `Content-Type` must match
4. Return accepted (with URLs) and rejected (with reasons)

**Definition of Done:**
- [ ] Endpoint validates file size and content type server-side
- [ ] Presigned URL generated with `generate_presigned_url('put_object', ...)` targeting quarantine bucket
- [ ] Presigned URL includes `Content-Length` and `Content-Type` conditions
- [ ] URL expiry set to 900 seconds (15 min)
- [ ] WikiFile records created in DB with `status = "pending_scan"`
- [ ] Rejected files returned with clear reason strings
- [ ] Manual test: get a presigned URL, upload a file to quarantine via curl

### Step 3.2 — Upload confirmation endpoint

```
POST /api/wikis/{wiki_id}/uploads/confirm
```

Request:
```python
class ConfirmUploadRequest(BaseModel):
    file_ids: list[str]   # WikiFile IDs that were successfully PUT to S3
```

Logic:
1. For each file_id, verify the object exists in quarantine (`s3.head_object`)
2. Set `scan_started_at = now()` on the WikiFile record
3. Return confirmation

**Definition of Done:**
- [ ] Endpoint verifies S3 object existence before confirming
- [ ] `scan_started_at` timestamp set (this starts the 5-min timeout clock)
- [ ] Files that don't exist in S3 are flagged as `failed_upload`

### Step 3.3 — Scan status polling endpoint

```
GET /api/wikis/{wiki_id}/uploads/status
```

Response:
```python
class FileStatusResponse(BaseModel):
    file_id: str
    filename: str
    relative_path: str
    status: str           # pending_scan | clean | failed_scan | failed_timeout
    scanned_at: datetime | None

class UploadStatusResponse(BaseModel):
    files: list[FileStatusResponse]
    all_complete: bool    # True when no files are pending_scan
```

Logic:
1. Query all `WikiFile` records for this wiki where `status = "pending_scan"`
2. For each, check the S3 object tag `GuardDutyMalwareScanStatus` via `s3.get_object_tagging`
3. If tag == `NO_THREATS_FOUND`:
   - Copy object from quarantine → wiki bucket
   - Delete from quarantine
   - Update DB: `status = "clean"`, `transferred_at = now()`
4. If tag == `THREATS_FOUND`:
   - Delete from quarantine
   - Update DB: `status = "failed_scan"`
5. If no tag yet and `scan_started_at + 5 min < now()`:
   - Update DB: `status = "failed_timeout"`
6. If no tag yet and within 5 min: leave as `pending_scan`
7. Also return any recently completed files (clean/failed in last 60s) so frontend catches transitions

**Definition of Done:**
- [ ] Endpoint reads GuardDuty tags from S3 and updates DB status accordingly
- [ ] Clean files are copied to wiki bucket and deleted from quarantine
- [ ] Failed files are deleted from quarantine
- [ ] Timeout enforced at 5 minutes from `scan_started_at`
- [ ] Response includes `all_complete` flag for frontend to know when to stop polling
- [ ] Manual test: upload a file, poll status, verify it transitions to clean

### Step 3.4 — List wiki files endpoint

```
GET /api/wikis/{wiki_id}/files
```

Returns all files for a wiki (clean only by default, `?include_pending=true` for all).

**Definition of Done:**
- [ ] Returns files with metadata (filename, path, size, status, timestamps)
- [ ] Defaults to clean files only
- [ ] `include_pending` query param shows all statuses

---

## Phase 4: Frontend — Upload Store & Queue

### Step 4.1 — Create uploads Pinia store

**File:** `frontend/src/stores/uploads.js`

State:
```js
{
  batches: Map<batchId, {
    wikiId: string,
    files: Map<fileId, {
      // Identity
      fileId: string | null,     // From backend after presign
      file: File,                // Browser File object
      filename: string,
      relativePath: string,      // Folder path (from webkitRelativePath or entry walk)
      sizeBytes: number,
      contentType: string,

      // State
      status: 'validating' | 'rejected' | 'queued' | 'uploading' | 'pending_scan' | 'clean' | 'failed_scan' | 'failed_timeout' | 'failed_upload',
      rejectReason: string | null,
      uploadProgress: number,    // 0-100 for uploading state
      presignedUrl: string | null,
      s3Key: string | null,
    }>,
    startedAt: Date,
  }>,
  activeBatchId: string | null,
}
```

Actions:
```
addFiles(wikiId, fileList)       → validate, create batch, split accepted/rejected
startUpload(batchId)             → request presigned URLs, begin upload queue
cancelFile(batchId, localId)     → cancel queued/uploading file
retryFile(batchId, localId)      → retry failed file
cancelBatch(batchId)             → cancel all pending in batch
```

Getters:
```
activeBatch                      → current batch being shown
overallProgress(batchId)         → { uploaded, scanning, complete, failed, total, bytesUploaded, bytesTotal }
filesByFolder(batchId)           → files grouped by top-level folder for tree display
```

**Definition of Done:**
- [ ] Store manages batches with per-file state tracking
- [ ] `addFiles` validates size (10MB) and type client-side, splits into accepted/rejected
- [ ] Folder-relative paths extracted from `webkitRelativePath` or `DataTransferItem` entry walking
- [ ] Store is global (persists across route navigation)

### Step 4.2 — Upload queue with concurrency control

**In:** `frontend/src/stores/uploads.js`

Logic:
1. `startUpload` calls `POST /api/wikis/{id}/uploads/presign` with all accepted files
2. Merge backend rejections (size mismatch, etc.) into file state
3. Start upload pool: max 4 concurrent `XMLHttpRequest` PUT requests
4. Each XHR:
   - Sets `Content-Type` header
   - Tracks `upload.onprogress` → updates `uploadProgress` (0-100)
   - On success → set status to `pending_scan`, call confirm endpoint
   - On error → set status to `failed_upload`
5. When a slot frees up, dequeue next `queued` file
6. When all uploads complete → start scan polling

**Definition of Done:**
- [ ] Max 4 concurrent uploads enforced (queue drains as slots free)
- [ ] Per-file upload progress tracked via XHR `progress` events
- [ ] Upload errors handled gracefully (file marked `failed_upload`, queue continues)
- [ ] Confirm endpoint called per-file on successful upload
- [ ] `beforeunload` warning set when uploads are in progress

### Step 4.3 — Scan status polling

**In:** `frontend/src/stores/uploads.js`

Logic:
1. After all uploads in a batch are confirmed, start polling `GET /api/wikis/{id}/uploads/status` every 5 seconds
2. Update per-file status from response
3. Stop polling when `all_complete === true`

**Definition of Done:**
- [ ] Polling starts after upload phase completes
- [ ] Per-file status updated reactively (UI updates automatically)
- [ ] Polling stops on `all_complete` or when batch is cancelled
- [ ] Polling interval: 5 seconds via `setInterval`, cleaned up on stop

---

## Phase 5: Frontend — Upload Manager UI

### Step 5.1 — File picker + drop zone component

**File:** `frontend/src/components/upload/FileDropZone.vue`

Supports:
- Click to open file picker (single/multi via `<input type="file" multiple>`)
- Click to open folder picker (via `<input type="file" webkitdirectory>`)
- Drag-and-drop files and folders (via `DataTransferItem.webkitGetAsEntry()` to walk folder trees recursively)

On file selection:
1. Walk entries, build flat list with `relativePath` for each file
2. Call `uploads.addFiles(wikiId, files)`

**Definition of Done:**
- [ ] Three input modes: file picker, folder picker, drag-and-drop
- [ ] Folder drag-and-drop recursively walks subdirectories
- [ ] `relativePath` preserved for each file (empty string for flat files)
- [ ] Drop zone has visual feedback (drag hover state)
- [ ] Emits to parent when files are added (to trigger drawer open)

### Step 5.2 — Upload manager drawer

**File:** `frontend/src/components/upload/UploadDrawer.vue`

Layout (slides in from bottom or right):
```
┌──────────────────────────────────────────────────┐
│ Upload to "{wiki.name}"           12/47 files    │
│ ████████████░░░░░░░░░░░░░░░░  38%    12.4 MB    │
│                                                  │
│ ▼ policies/                      2/5 ready       │
│   ├ ✓ attendance.pdf      2.1MB  Clean           │
│   ├ ⏳ grading.docx       1.4MB  Scanning...     │
│   ├ ↑ leave.pdf           3.2MB  Uploading 67%   │
│   ├ ○ moonlighting.pdf    0.8MB  Queued          │
│   └ ○ duty-hours.pdf      1.1MB  Queued          │
│ ▼ handbooks/                     1/2 ready       │
│   ├ ✓ resident.pdf        4.2MB  Transferred     │
│   └ ⏳ faculty.docx       2.8MB  Scanning...     │
│ ✕ Files with errors                              │
│   └ ✕ video.mp4          48.2MB  Too large       │
│                                                  │
│        [ Cancel ]                                │
└──────────────────────────────────────────────────┘
```

Components to build:
- `UploadDrawer.vue` — outer shell with aggregate progress bar, open/close toggle
- `UploadFolderGroup.vue` — collapsible folder with summary count
- `UploadFileRow.vue` — single file with status icon, name, size, progress bar, action buttons

**Definition of Done:**
- [ ] Drawer shows/hides based on active batch presence
- [ ] Aggregate progress bar: bytes uploaded / total bytes (smooth)
- [ ] File counter: completed / total
- [ ] Files grouped by top-level folder (collapsible), flat files under "Files"
- [ ] Per-file: status icon + label (see state table), inline progress bar for uploading
- [ ] Rejected files shown at bottom with red icon + reason
- [ ] Cancel button for entire batch
- [ ] Retry button on individual failed files
- [ ] `beforeunload` warning while uploads active

### Step 5.3 — Integrate into Wiki detail view

**File:** `frontend/src/views/WikiDetailView.vue` (new view)
**Route:** `/wikis/:id`

This view shows:
- Wiki name + description
- File list (clean files from `GET /api/wikis/{id}/files`)
- `FileDropZone` component for uploading
- `UploadDrawer` component (visible when a batch is active)

**File:** `frontend/src/views/WikiListView.vue` (new view)
**Route:** `/wikis`

Shows all wikis as cards. "Create Wiki" button for admins.

**Definition of Done:**
- [ ] Both views created and registered in router
- [ ] Sidebar updated with "Wikis" nav link
- [ ] WikiDetailView shows file list + drop zone + upload drawer
- [ ] WikiListView shows wiki cards with file counts
- [ ] Create Wiki modal/form for admin users

---

## Phase 6: Integration Test & Hardening

### Step 6.1 — End-to-end manual test

Test matrix:
1. Create a wiki as admin
2. Upload a single small file → verify quarantine → clean → wiki bucket
3. Upload multiple files at once → verify concurrency (4 max) + progress
4. Upload a folder with subfolders → verify paths preserved in S3 keys
5. Upload a 15MB file → verify client-side rejection (never hits backend)
6. Upload a .exe file → verify client-side rejection
7. Upload during scan → verify progress shows upload + scanning phases correctly
8. Navigate away during upload → verify `beforeunload` warning
9. Cancel a queued file → verify it's removed from queue
10. Retry a failed file → verify it re-enters queue

**Definition of Done:**
- [ ] All 10 test scenarios pass
- [ ] No console errors during upload flows
- [ ] S3 objects land in correct buckets with correct keys
- [ ] DB records match S3 state

### Step 6.2 — Error handling & edge cases

- [ ] Backend: handle S3 `ClientError` exceptions (bucket doesn't exist, access denied, throttling)
- [ ] Backend: handle case where GuardDuty is not configured (tag never appears → timeout)
- [ ] Frontend: handle presign endpoint failure (show error, don't leave files stuck in "queued")
- [ ] Frontend: handle network disconnect during upload (retry-able error state)
- [ ] Frontend: duplicate filename in same folder — append counter (`handbook (1).pdf`)
- [ ] Frontend: empty folder upload (no error, just no files added)

---

## File Inventory

### New files
```
backend/app/models/wiki.py
backend/app/models/wiki_file.py
backend/app/api/wikis.py
backend/app/api/uploads.py
backend/migrations/002_create_wiki_schema_and_tables.sql
frontend/src/stores/uploads.js
frontend/src/components/upload/FileDropZone.vue
frontend/src/components/upload/UploadDrawer.vue
frontend/src/components/upload/UploadFolderGroup.vue
frontend/src/components/upload/UploadFileRow.vue
frontend/src/views/WikiListView.vue
frontend/src/views/WikiDetailView.vue
```

### Modified files
```
backend/app/models/__init__.py          → export Wiki, WikiFile
backend/app/core/database.py            → add "app" schema creation in init_db()
backend/app/core/aws.py                 → add presigned URL generation helper
backend/app/main.py                     → register wiki + upload routers
frontend/src/router/index.js            → add /wikis and /wikis/:id routes
frontend/src/App.vue                    → add "Wikis" sidebar nav link
```

---

## Execution Order

```
Phase 1 (Steps 1.1–1.3)  →  can be done in one shot, no dependencies
Phase 2 (Step 2.1)        →  depends on Phase 1 models
Phase 3 (Steps 3.1–3.4)   →  depends on Phase 2 (needs wiki to exist)
Phase 4 (Steps 4.1–4.3)   →  depends on Phase 3 APIs existing
Phase 5 (Steps 5.1–5.3)   →  depends on Phase 4 store
Phase 6 (Steps 6.1–6.2)   →  integration, depends on all above
```

Phases 4+5 frontend work can start in parallel with Phase 3 backend work if API contracts are agreed upfront.
