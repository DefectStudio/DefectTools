ALTER TABLE jobs ADD COLUMN resubmit_request_id TEXT;

CREATE UNIQUE INDEX jobs_resubmit_request_idx
    ON jobs (resubmit_request_id)
    WHERE resubmit_request_id IS NOT NULL;
