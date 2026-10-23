-- Chunk 7b: one row per backup attempt. No content.
-- build-engineer-Opus5.5-agent, 2026-10-23
create table backup_runs (
    id          bigserial primary key,
    started_at  timestamptz not null default now(),
    finished_at timestamptz,
    outcome     text not null default 'running' check (outcome in ('running', 'ok', 'failed', 'skipped')),
    object_key  text,
    bytes       bigint,
    sha256      text,
    error_class text
);
create index backup_runs_time on backup_runs (started_at desc);
