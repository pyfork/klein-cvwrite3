-- Chunk 7v (Addendum 8): "Keep my applications for 3 months". One flag per account, off by default; the nightly
-- retention job keeps a flagged account's runs and PDFs 3 months instead of 30 days. Additive: a not-null column with
-- a default, so older code ignores it.
-- build-engineer-Sonnet5.5-agent, 2026-10-27
alter table accounts add column if not exists keep_applications boolean not null default false;
