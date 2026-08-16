PRAGMA foreign_keys = OFF;
DELETE FROM job_events;
DELETE FROM job_attempts;
DELETE FROM job_blacklist;
DELETE FROM workers;
DELETE FROM jobs;
PRAGMA foreign_keys = ON;
