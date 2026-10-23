-- Chunk 7a: the account page, deleting an account, and the 30-day purge of CVs and PDFs.
-- build-engineer-Opus5.5-agent, 2026-10-23

-- A purged run keeps only what accounting and the funnel need: no ad, no ad read, no CV text.
alter table runs alter column ad_text drop not null;
alter table runs drop constraint runs_ad_text_check;
alter table runs add constraint runs_ad_text_check check (ad_text is null or length(ad_text) between 200 and 30000);
alter table runs add column purged_at timestamptz;

-- Set when the account is deleted, with the refund the user asked for before deleting (if any).
alter table accounts add column deleted_at timestamptz;
alter table accounts add column refund_requested_rm numeric(8, 2);

-- An order still pending when its account is deleted: refund it if the money arrives.
alter table orders add column flag text;

-- One row per deleted account: a hash of the account id, and the date. No personal data.
-- Replayed after any restore from backup, so a deleted account stays deleted.
create table tombstones (
    hash        text primary key check (hash ~ '^[0-9a-f]{64}$'),
    deleted_on  date not null default current_date
);
