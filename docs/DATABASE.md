# Database Design

All money is stored as **integer Toman**. All traffic is stored in **bytes**
(matching the 3X-UI API). Timestamps are timezone-aware UTC.

## Tables & key fields

### users
| field | type | notes |
|---|---|---|
| id | PK | |
| telegram_id | bigint, unique | |
| username, full_name | str | kept fresh on each message |
| role | enum(user, reseller, admin, super_admin) | |
| balance | bigint | wallet, Toman |
| referral_code | str, unique | `ref_<telegram_id>` |
| referred_by_id | FK→users.id | who invited this user |
| bonus_gb | float | referral GB stacked on free quota |
| price_multiplier | float | reseller pricing |
| is_banned, ban_reason | | anti-abuse |
| joined_at | datetime | account-age fraud signal |

### panels  (multi-server)
`base_url, username, password` (panel login) · `public_host` (client connect
host) · `sub_enabled`, `sub_base_url` (Subscription Server) · `weight`,
`is_active`, `is_healthy`, `last_health_check`.

### inbounds  (cached from panel)
`panel_id` FK · `inbound_id` (id on panel) · `protocol`, `port`,
`stream_settings` (JSON text) — used by `sub_builder`. Unique(panel_id, inbound_id).

### plans
`title, description, volume_gb (0=∞), duration_days (0=∞), price, is_active,
sort_order`. **M2M** with `inbounds` via `plan_inbounds` → each plan maps to
one or more inbounds used to build its config.

### subscriptions  (a provisioned client)
`user_id`, `panel_id`, `plan_id` · `kind` (free/paid/referral) ·
`status` (active/expired/disabled/pending) · `client_uuid`, `client_email`
(unique id on panel), `sub_id` · `total_bytes`, `up_bytes`, `down_bytes`,
`expire_at` · `warned_volume`, `warned_expiry` (alert dedupe) · `sub_link` (cached).

### transactions  (wallet ledger)
`user_id`, `type` (topup/purchase/referral_reward/refund/admin_adjust),
`amount` (+/−), `balance_after`, `description`, `ref_payment_id`.

### referrals
`inviter_id`, `invitee_id` (unique), `bonus_gb_granted`, `revenue_earned`.

### payments  (card-to-card receipts)
`user_id`, `purpose` (wallet_topup/plan_purchase), `amount`, `plan_id`,
`status` (pending/approved/rejected), `receipt_file_id` (Telegram),
`admin_message_id`, `reviewed_by`, `review_note`, `reviewed_at`.

### discount_codes
`code` (unique), `percent`, `max_uses`, `used_count`, `expires_at`, `is_active`.

### tickets
`user_id`, `message`, `is_open`, `admin_reply`.

### settings  (runtime key/value)
`key` PK, `value`. Seeded from `.env`, editable live from the admin panel
(free_quota_gb, free_period_days, referral_bonus_gb, referral_topup_percent,
sales_enabled, card_number, card_holder).

## Relationships (ER summary)
```
users 1───* subscriptions *───1 plans *───* inbounds *───1 panels
users 1───* transactions
users 1───* payments *──1 plans
users 1───* referrals (inviter)      users 1──1 referrals (invitee)
users *──1 users (referred_by)
```
