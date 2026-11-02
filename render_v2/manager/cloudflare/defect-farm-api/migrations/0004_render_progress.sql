-- A render-progress receipt is distinct from the worker lease heartbeat.
ALTER TABLE jobs ADD COLUMN progress_details_json TEXT;
