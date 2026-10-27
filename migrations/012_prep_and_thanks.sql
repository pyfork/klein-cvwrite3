-- Chunk 7w (Addendums 11 and 12): interview prep notes on a run, and the "sent" mark that keeps the
-- payment-confirmed email once per order. Additive: nullable columns, so older code ignores them.
-- build-engineer-Opus5.5-agent, 2026-10-27
alter table runs add column if not exists interview_prep jsonb;
alter table orders add column if not exists thanked_at timestamptz;
alter table feedback drop constraint if exists feedback_reason_check;
alter table feedback add constraint feedback_reason_check
    check (reason in ('problem', 'keywords', 'long', 'wording', 'prep', 'other'));
