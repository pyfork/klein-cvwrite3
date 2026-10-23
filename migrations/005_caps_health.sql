-- Chunk 6: "not good" feedback, problem reports, errors, degraded events, uptime checks.
-- build-engineer-Opus5.5-agent, 2026-10-23

-- A signal only: it feeds the admin funnel, and nothing is rewritten.
create table feedback (
    run_id      bigint primary key references runs (id),
    account_id  bigint not null references accounts (id),
    reason      text not null check (reason in ('problem', 'keywords', 'long', 'wording', 'other')),
    created_at  timestamptz not null default now()
);

create table problem_reports (
    id          bigserial primary key,
    account_id  bigint references accounts (id),       -- the link to the person; deleted with the account
    email       text not null check (email = lower(email)),
    category    text not null check (category in ('broke', 'paid', 'output', 'privacy', 'other')),
    body        text not null default '' check (length(body) <= 2000),
    run_id      bigint references runs (id),
    order_id    bigint references orders (id),
    page        text not null default '' check (length(page) <= 200),
    request_id  text not null default '',
    app_version text not null default '',
    status      text not null default 'open' check (status in ('open', 'answered', 'closed')),
    reply       text check (length(reply) <= 2000),
    created_at  timestamptz not null default now(),
    answered_at timestamptz,
    closed_at   timestamptz
);
create index problem_reports_open on problem_reports (status, created_at);

-- Unexpected exceptions: an error class, where, and a traceback with file, line and function only.
create table errors (
    id          bigserial primary key,
    error_class text not null,
    route       text not null default '',
    run_id      bigint,
    request_id  text not null default '',
    traceback   text not null default '',
    created_at  timestamptz not null default now()
);
create index errors_time on errors (created_at);

-- A ceiling breached: from `started_at` until `ended_at` (open while null).
create table degraded_events (
    id          bigserial primary key,
    kind        text not null check (kind in ('generation_p95', 'rerender_p95', 'queue_wait', 'failure_rate')),
    step        text not null,
    value       numeric not null,
    ceiling     numeric not null,
    started_at  timestamptz not null default now(),
    ended_at    timestamptz
);
create unique index degraded_one_open on degraded_events (kind) where ended_at is null;

-- One row a minute from the healthz timer. Missing minutes count as down.
create table uptime_checks (
    id          bigserial primary key,
    checked_at  timestamptz not null default now(),
    ok          boolean not null,
    ms          integer not null,
    detail      text not null default ''
);
create index uptime_time on uptime_checks (checked_at);
