-- Chunk 7j: sign-in by a 6-digit code sent by email (replaces Cloudflare Access).
-- Codes and session tokens are stored only as HMACs; codes are keyed by a hash of the email, not the email.
-- build-engineer-Opus5.5-agent, 2026-10-24
create table login_codes (
    id          bigserial primary key,
    email_hash  text not null,
    ip_hash     text not null,
    code_hash   text not null,
    created_at  timestamptz not null default now(),
    expires_at  timestamptz not null,
    attempts    int not null default 0,
    used_at     timestamptz
);
create index login_codes_email on login_codes (email_hash, created_at desc);
create index login_codes_ip on login_codes (ip_hash, created_at desc);
create index login_codes_time on login_codes (created_at);

create table sessions (
    token_hash   text primary key,
    email        text not null,
    created_at   timestamptz not null default now(),
    last_seen_at timestamptz not null default now(),
    expires_at   timestamptz not null
);
create index sessions_email on sessions (email);
