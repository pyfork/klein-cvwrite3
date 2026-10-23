-- Chunk 3: profile, one ad in -> one CV out, edit and re-render, the pause.
-- build-engineer-Opus5.5-agent, 2026-10-23

create table profiles (
    account_id      bigint primary key references accounts (id),
    master_text     text not null default '' check (length(master_text) <= 60000),
    master_name     text not null default '',
    name            text not null default '' check (length(name) <= 120),
    location        text not null default '' check (length(location) <= 120),
    phone           text not null default '' check (length(phone) <= 60),
    email           text not null default '' check (length(email) <= 200),
    links           text not null default '' check (length(links) <= 300),
    standing_edits  text not null default '' check (length(standing_edits) <= 2000),
    updated_at      timestamptz not null default now()
);

-- One CV for one ad. Holds the checkpoints (call A and B outputs), so a crash never pays Claude twice.
create table runs (
    id              bigserial primary key,
    account_id      bigint not null references accounts (id),
    status          text not null default 'generating'
                    check (status in ('generating', 'passed', 'failed', 'cancelled')),
    ad_text         text not null check (length(ad_text) between 200 and 30000),
    ad_read         jsonb,          -- call A, after the quote check
    draft_md        text,           -- call B, with {{NAME}} and {{CONTACT}}; replaced by each passing re-render
    gaps            jsonb,
    checks          jsonb,          -- the last check result
    drafts          integer not null default 0,   -- call B drafts so far: 1, or 2 after the internal retry
    pdf_rev         integer not null default 0,
    rerenders_used  integer not null default 0 check (rerenders_used between 0 and 3),
    failure         text,           -- an error class or check name, never content
    created_at      timestamptz not null default now(),
    passed_at       timestamptz
);
create index runs_account on runs (account_id, created_at desc);

-- Work for the worker: a generation, a re-render, or the owner's test render (no run). Claimed with FOR UPDATE SKIP LOCKED.
create table jobs (
    id           bigserial primary key,
    run_id       bigint references runs (id),
    kind         text not null check (kind in ('generate', 'rerender', 'test_render')),
    status       text not null default 'queued'
                 check (status in ('queued', 'running', 'held', 'done', 'failed', 'expired', 'cancelled')),
    input_text   text,             -- the user's edited text, for a re-render
    attempts     integer not null default 0,
    outcome      text,             -- passed | failed_check | blocked_pages | format_failed | ...
    message      text,             -- what the user sees; never CV content
    created_at   timestamptz not null default now(),
    started_at   timestamptz,
    finished_at  timestamptz,
    held_at      timestamptz
);
create index jobs_queue on jobs (status, created_at) where status in ('queued', 'running', 'held');

-- One row per step of a generation or re-render. No content.
create table run_steps (
    id             bigserial primary key,
    run_id         bigint references runs (id),
    job_id         bigint references jobs (id),
    step           text not null,  -- queue_wait | call_a | call_b | retry | render | check | reformat | test_render
    started_at     timestamptz not null,
    duration_ms    integer not null,
    outcome        text not null,  -- ok | fail | error
    model          text,
    input_tokens   integer,
    output_tokens  integer,
    error_class    text,
    memory_peak    bigint,         -- bytes, the render cgroup's memory.peak where available
    cpu_ms         integer
);
create index run_steps_time on run_steps (started_at);

-- One row per Claude call.
create table usage (
    id             bigserial primary key,
    run_id         bigint references runs (id),
    account_id     bigint references accounts (id),
    step           text not null,
    model          text not null,
    input_tokens   integer not null,
    output_tokens  integer not null,
    cost_usd       numeric(10, 6) not null,
    request_id     text,
    created_at     timestamptz not null default now()
);
create index usage_time on usage (created_at);

-- Paused means an open row (resumed_at is null).
create table system_pause (
    id          bigserial primary key,
    paused_at   timestamptz not null default now(),
    reason      text not null,
    source      text not null check (source in ('auto', 'owner')),
    resumed_at  timestamptz
);
create unique index system_pause_one_open on system_pause ((true)) where resumed_at is null;

-- A spend points at the run it paid for, once.
alter table credit_ledger add column run_id bigint unique references runs (id);
alter table credit_ledger add constraint spend_has_run check ((kind = 'spend') = (run_id is not null));
