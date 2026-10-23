-- Chunk 2: sign-in, the whitelist, access requests, consents, and the ledger's first rows.
-- build-engineer-Opus5.5-agent, 2026-10-23

-- One row per person who was ever approved. Holds no personal data, so it outlives a deleted
-- account: orders and the ledger point here, and `tag` is what they show after deletion.
create table accounts (
    id          bigserial primary key,
    tag         text not null unique,
    created_at  timestamptz not null default now()
);

-- The whitelist. Deleting an account deletes its row here, which cuts the link to the email.
create table allowed_users (
    email         text primary key check (email = lower(email)),
    account_id    bigint not null unique references accounts (id),
    approved_at   timestamptz not null default now(),
    approved_via  text not null check (approved_via in ('owner', 'wave2'))
);

create table access_requests (
    id          bigserial primary key,
    email       text not null check (email = lower(email)),
    note        text not null default '' check (length(note) <= 200),
    status      text not null default 'pending' check (status in ('pending', 'approved', 'declined')),
    created_at  timestamptz not null default now(),
    decided_at  timestamptz
);
create unique index access_requests_one_pending on access_requests (email) where status = 'pending';

create table settings (
    key    text primary key,
    value  jsonb not null
);
insert into settings (key, value) values ('wave2_auto_approve', 'false');

-- Kept 12 months after an account is deleted (proof of consent, and no repeat free credits).
create table consents (
    id                  bigserial primary key,
    email               text not null check (email = lower(email)),
    notice_version      text not null check (notice_version ~ '^[0-9]+\.[0-9]+$'),
    text_hash           text not null check (text_hash ~ '^[0-9a-f]{64}$'),
    lang                text not null check (lang in ('en', 'ms')),
    sensitive           boolean not null,
    created_at          timestamptz not null default now(),
    account_deleted_at  timestamptz
);
create index consents_email on consents (email, created_at desc);

-- Insert-only. Grants carry their own expiry; spends and refunds don't.
create table credit_ledger (
    id          bigserial primary key,
    account_id  bigint not null references accounts (id),
    delta       integer not null check (delta <> 0),
    kind        text not null check (kind in ('free', 'pack', 'spend', 'refund')),
    expires_at  timestamptz,
    created_at  timestamptz not null default now(),
    check ((kind in ('free', 'pack')) = (delta > 0 and expires_at is not null))
);
create index credit_ledger_account on credit_ledger (account_id, created_at);

create function credit_ledger_insert_only() returns trigger language plpgsql as $$
begin
    raise exception 'credit_ledger is insert-only';
end $$;
create trigger credit_ledger_no_update before update or delete on credit_ledger
    for each row execute function credit_ledger_insert_only();
create trigger credit_ledger_no_truncate before truncate on credit_ledger
    for each statement execute function credit_ledger_insert_only();
