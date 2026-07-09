# Security Notes & Future Development

## Security checklist (implemented)
- **Secrets in `.env`** only; `.gitignore` excludes `.env`, `data/`, `backups/`,
  `*.db`. No credentials hardcoded.
- **Rate limiting** (`ThrottlingMiddleware`) drops floods per user.
- **Force-join** gate before any feature is usable.
- **Anti-fraud** on free configs: one per Telegram ID per month + brand-new
  account / no-username heuristic (`utils/security.looks_suspicious`).
- **Auditable wallet**: every balance change writes a `transactions` row with
  running `balance_after`.
- **Panel client** validates the JSON envelope, re-logs in on 401/403, and
  retries transient network errors with exponential backoff.
- **Role-based admin** (`IsAdmin` filter; super-admins from `.env`).
- **User-friendly errors**: handlers catch `PanelError`/exceptions and show a
  generic Persian message while logging the detail.

## Hardening recommendations (before production)
1. **Panel over HTTPS** with a valid cert; set `verify_ssl=True` in `XUIClient`
   once your panel cert is trusted (currently relaxed for self-signed panels).
2. **Encrypt panel passwords at rest** (e.g. Fernet with a key in `.env`) instead
   of storing plaintext in the `panels` table.
3. **Redis FSM storage** for multi-instance deployments (MemoryStorage is
   single-process).
4. **Idempotency** on payment approval (already guarded by `status != PENDING`);
   add a DB unique constraint per `(admin_message_id)` if needed.
5. **Least-privilege admin group**: only trusted admins should have the group;
   approval callbacks re-check `is_admin()` server-side (they do).
6. **Backups off-box**: ship `backups/` to object storage (S3/GCS) via a cron.
7. **Input validation**: amounts are integer-checked; extend with min/max caps.
8. **Webhook mode + reverse proxy** (nginx) for higher throughput than polling.

## Future development
- Full admin CRUD screens (plans, panels, inbound mapping, user search/ban/adjust).
- Discount codes + campaigns wired into checkout (`discount_codes` table ready).
- Reseller portal with `price_multiplier` and sub-balance.
- Auto gateway payments (Zarinpal/IDPay) alongside card-to-card.
- Traffic graphs & per-plan revenue reports.
- Multi-language (extract `utils/texts.py` into per-locale files).
- Auto-migrate users off unhealthy panels; capacity-aware panel selection.
- Prometheus metrics + alerting on panel downtime.
