-- Chunk 7n: open sign-ups up to the cap, then a waitlist. A waitlisted person may ask for one email when
-- there's room (the owner presses "Email the waitlist"). Additive: two columns with defaults.
-- build-engineer-Opus5.5-agent, 2026-10-25
alter table access_requests add column if not exists notify boolean not null default false;
alter table access_requests add column if not exists notified_at timestamptz;
