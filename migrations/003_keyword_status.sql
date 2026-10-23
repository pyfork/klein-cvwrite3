-- Each top-3 keyword's status from call B: backed | bridged | missing. Only backed and bridged are checked.
-- build-engineer-Opus5.5-agent, 2026-10-23
alter table runs add column keyword_status jsonb;
