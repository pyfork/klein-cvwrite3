-- Chunk 7t (UX audit): two nullable columns on runs. ad_hash tells two runs are the same ad, for "try again at most
-- 2 times per ad" (Addendum 1); opened_at is when the user first opened a finished CV, for the "your CV is ready" bar.
-- Additive: no defaults needed, old code ignores both. Runs that already passed count as opened, so the first deploy
-- doesn't light the bar for CVs people have seen.
-- build-engineer-Sonnet5.5-agent, 2026-10-27
alter table runs add column if not exists ad_hash text;
alter table runs add column if not exists opened_at timestamptz;
create index if not exists runs_account_ad_hash on runs (account_id, ad_hash) where ad_hash is not null;
update runs set opened_at = coalesce(passed_at, created_at) where status = 'passed' and opened_at is null;
