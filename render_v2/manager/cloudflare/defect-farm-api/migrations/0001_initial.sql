PRAGMA foreign_keys = ON;

CREATE TABLE jobs (
    id TEXT PRIMARY KEY,
    batch_id TEXT,
    project TEXT NOT NULL,
    job_type TEXT NOT NULL,
    shot_name TEXT NOT NULL,
    render_version INTEGER,
    status TEXT NOT NULL CHECK (
        status IN ('queued', 'rendering', 'complete', 'failed', 'canceled')
    ),
    priority INTEGER NOT NULL DEFAULT 50,
    submitted_at TEXT NOT NULL,
    submitted_by TEXT,
    submitted_user TEXT,
    updated_at TEXT NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    worker_id TEXT,
    lease_token TEXT UNIQUE,
    lease_expires_at INTEGER,
    claimed_at TEXT,
    render_started_at TEXT,
    render_finished_at TEXT,
    progress REAL NOT NULL DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    result_json TEXT CHECK (result_json IS NULL OR json_valid(result_json)),
    last_failure_json TEXT CHECK (
        last_failure_json IS NULL OR json_valid(last_failure_json)
    ),
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
    resubmitted_from_job_id TEXT,
    revision INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (resubmitted_from_job_id) REFERENCES jobs(id) ON DELETE SET NULL
) STRICT;

CREATE INDEX jobs_dispatch_order_idx
    ON jobs (status, priority DESC, submitted_at ASC, id ASC);
CREATE INDEX jobs_lease_expiration_idx
    ON jobs (status, lease_expires_at)
    WHERE status = 'rendering';
CREATE INDEX jobs_project_submitted_idx
    ON jobs (project, submitted_at DESC);
CREATE INDEX jobs_batch_idx ON jobs (batch_id);
CREATE INDEX jobs_shot_version_idx ON jobs (project, shot_name, render_version);

CREATE TABLE job_blacklist (
    job_id TEXT NOT NULL,
    worker_id TEXT COLLATE NOCASE NOT NULL,
    reason TEXT,
    created_at TEXT NOT NULL,
    attempt_number INTEGER,
    PRIMARY KEY (job_id, worker_id),
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
) WITHOUT ROWID;

CREATE TABLE job_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    attempt_number INTEGER NOT NULL,
    worker_id TEXT COLLATE NOCASE NOT NULL,
    lease_token TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK (
        status IN ('rendering', 'complete', 'failed', 'released', 'lease_expired')
    ),
    claimed_at TEXT NOT NULL,
    finished_at TEXT,
    result_json TEXT CHECK (result_json IS NULL OR json_valid(result_json)),
    UNIQUE (job_id, attempt_number),
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
) STRICT;

CREATE INDEX job_attempts_job_idx ON job_attempts (job_id, attempt_number DESC);
CREATE INDEX job_attempts_worker_idx ON job_attempts (worker_id, claimed_at DESC);

CREATE TABLE job_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    worker_id TEXT COLLATE NOCASE,
    attempt_number INTEGER,
    details_json TEXT CHECK (details_json IS NULL OR json_valid(details_json)),
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
) STRICT;

CREATE INDEX job_events_job_idx ON job_events (job_id, id DESC);

CREATE TABLE workers (
    id TEXT PRIMARY KEY COLLATE NOCASE,
    display_name TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('waiting', 'rendering', 'offline', 'stopped')
    ),
    current_job_id TEXT,
    stop_requested INTEGER NOT NULL DEFAULT 0 CHECK (stop_requested IN (0, 1)),
    stop_requested_at TEXT,
    app_version TEXT,
    capabilities_json TEXT CHECK (
        capabilities_json IS NULL OR json_valid(capabilities_json)
    ),
    FOREIGN KEY (current_job_id) REFERENCES jobs(id) ON DELETE SET NULL
) STRICT;

CREATE INDEX workers_last_seen_idx ON workers (last_seen_at DESC);
