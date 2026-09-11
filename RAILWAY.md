# Railway deployment

This build is designed for Railway Cron Jobs.

## Service settings

- Start command: `python main.py`
- Cron schedule: `0 */12 * * *`
- Cron timezone: UTC (Railway cron schedules are UTC)
- Restart policy: Never

The app performs one monitoring cycle and exits. Railway starts it again on the cron schedule.

## Variables

Set these Railway service variables:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `MONITOR_DB_PATH=/data/monitor.db`

Do not commit a real Telegram token to GitHub.

## Persistent state

Attach a Railway Volume to the service at `/data`.
The SQLite database will be stored at `/data/monitor.db`, preserving notification history across cron runs and deployments.

Without the volume, the monitor still works, but its SQLite history can be lost when a new container is created, which may cause repeat notifications.
