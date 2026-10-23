-- Chunk 5: orders paid by DuitNow QR, credited by the owner once the money is seen in the bank.
-- build-engineer-Opus5.5-agent, 2026-10-23

create table orders (
    id           bigserial primary key,
    account_id   bigint not null references accounts (id),
    ref          text not null unique check (ref ~ '^CV3-[A-HJ-NP-Z2-9]{4}$'),
    credits      integer not null check (credits in (5, 20)),
    amount_rm    numeric(8, 2) not null check (amount_rm > 0),
    status       text not null default 'pending' check (status in ('pending', 'approved', 'rejected', 'cancelled')),
    paid_at      timestamptz,            -- when the user pressed "I've paid"; never a reason to add credits
    decided_at   timestamptz,
    reason       text check (length(reason) <= 300),   -- shown to the user on a rejection
    created_at   timestamptz not null default now(),
    check ((status = 'rejected') = (reason is not null))
);
create index orders_status on orders (status, created_at);
create unique index orders_one_open on orders (account_id) where status = 'pending' and paid_at is null;

-- A pack grant points at the order it paid for, once.
alter table credit_ledger add column order_id bigint unique references orders (id);
alter table credit_ledger add constraint pack_has_order check ((kind = 'pack') = (order_id is not null));
