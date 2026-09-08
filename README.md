# KCC Gala call watcher

Daily free check of the Korean Cultural Centre Canada **Notices** board for a K-Pop Gala dancer/team open call. Posts to Discord when a new match appears.

Watches: https://canada.korean-culture.org/en/1117/board/580/list

## 1. Preview (no Discord)

```bash
python3 check.py --dry-run
```

Prints raw hits, year exclusions (2024/2025), already-notified lines, and what would notify. Does not write `notified.txt` or call Discord.

If `DISCORD_WEBHOOK_URL` is unset, live mode also stays print-only.

## 2. Discord webhook

1. Discord channel → Edit Channel → Integrations → Webhooks → New Webhook
2. Copy the webhook URL

## 3. GitHub Actions

1. Push this repo to GitHub (public is fine for free Actions)
2. Settings → Secrets and variables → Actions → New repository secret
   - Name: `DISCORD_WEBHOOK_URL`
   - Value: your webhook URL
3. Actions → **Watch KCC Gala call** → Run workflow

The watch workflow runs daily at 14:00 UTC (~10:00 ET in daylight time). When it notifies, it appends matches to `notified.txt` and commits so each distinct match only alerts once.

A separate workflow sends a quiet **“still watching”** Discord ping on **Sundays** at 15:00 UTC (~11:00 ET). Run it manually via Actions → **Weekly still-watching ping**.

## Matching

Recall-first patterns around `gala` + call/dancer/team/register/apply/audition. Spans containing `2024` or `2025` are skipped. Known old titles are also seeded in `notified.txt`.
