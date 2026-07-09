# Core Logic Flowcharts

## 1) Free monthly config
```
User taps "🎁 کانفیگ رایگان"
        │
        ▼
free_config_service.eligibility()
  ├─ banned?              ─► reject (banned msg)
  ├─ suspicious account?  ─► reject (need username/older account)
  ├─ already claimed this month? ─► show reset date
  └─ OK ▼
subscription_service.provision(kind=FREE,
    volume = free_quota_gb + user.bonus_gb, days = free_period_days)
        │  (add client to mapped inbound(s) on picked panel)
        ▼
build sub link  ─►  send to user
```

## 2) Referral
```
New user opens t.me/Bot?start=ref_<id>
        ▼
start handler → user_service.get_or_create()
        ▼
referral_service.register_referral(inviter, invitee)
  ├─ self / already-referred? ─► skip
  └─ bind invitee.referred_by = inviter
     inviter.bonus_gb += referral_bonus_gb   (stacks on free quota)
        ▼
(later) invitee tops up wallet → payment approved
        ▼
referral_service.reward_topup(invitee, amount)
  reward = amount * referral_topup_percent / 100
  credit inviter wallet (system-funded; invitee balance untouched)
```

## 3) Paid purchase (two paths)
```
User taps "🛒 خرید" → choose plan
   ├─ "💳 پرداخت با کیف پول"
   │      balance >= price? ── no ─► ask to top up
   │      yes ▼
   │      wallet debit + provision(kind=PAID) ─► send sub link
   │
   └─ "🧾 کارت‌به‌کارت"
          show card + amount → user sends receipt photo
                 ▼
          payment_service.create_pending(PLAN_PURCHASE)
                 ▼
          post receipt to admin group with ✅/❌
                 ▼  (see flow 4)
```

## 4) Payment approval (admin)
```
Receipt in admin group → admin taps ✅ / ❌
        │
   ✅ approve                         ❌ reject
        ▼                                 ▼
payment_service.approve()          payment_service.reject(note)
  topup?  → credit wallet                mark REJECTED
          → referral reward to inviter   notify user (rejected)
  purchase?→ provision(kind=PAID)
        ▼
 notify user (sub link) + edit admin msg
```

## 5) Scheduled jobs (APScheduler)
```
every 30m  sync_all_usage   → pull up/down/expiry from panels
every 60m  check_alerts     → warn at 80% volume / ≤3 days to expiry
every 10m  health_check     → mark panels healthy/unhealthy
daily 03:00 backup_db       → dump + prune old backups
monthly 1st reset_free_quota→ reset warning flags (new-month eligibility auto)
```
