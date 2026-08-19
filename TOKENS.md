# Token usage tracking — StaffDPapp

LLM token usage for this project, tallied session by session.

## Cumulative tally (2026-08-19)

| Metric | Value |
|---|---|
| Dev sessions (Hermes) | 19 |
| Scripted agent sessions (API) | 0 |
| Models | deepseek-v4-flash, deepseek-v4-pro |
| Messages | 3 611 |
| API calls | 3 056 |
| Input tokens | 6 700 769 |
| Output tokens | 1 478 664 |
| Of which reasoning | 502 360 |
| Cache read (cache_read) | 449 046 016 |
| Cache write (cache_write) | 0 |
| **Total (input + output)** | **8 179 433** |
| Estimated cost | ≈ 3.21 USD |

## How to re-read the counter

The Hermes session database (SQLite) holds the exact counters:

```bash
sqlite3 ~/.hermes/state.db "SELECT id, started_at, model,
  input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
  reasoning_tokens, estimated_cost_usd
  FROM sessions WHERE cwd LIKE '%staff-delegation%'
  ORDER BY started_at;"
```

After each dev session, copy the matching row into the table above.

## Notes

- Tally taken from `~/.hermes/state.db` — sessions matched by
  `cwd LIKE '%staff-delegation%'` / title, plus 5 sessions attributed by
  title + first user message (deploy 2026.08.018, designations on prod,
  prod outage diagnostics, survey module proposal, prod incident 2026-08-19).
  Aggregated per session × model from `session_model_usage` (the reliable
  source on current installs — `sessions` still carries counters on this
  machine but `session_model_usage` is authoritative).
- « Scripted agent sessions (API) » = `api-*` sessions driven by scripts
  (audits, releases, background tasks) attached to this project.
- `reasoning_tokens` is probably included in `output_tokens`
  (to be confirmed with the provider).
- The session in progress at tally time is not flushed yet — it will appear
  in the next tally.
- Tally generated on 2026-08-19 from the session database.
