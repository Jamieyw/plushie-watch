# plushie-watch

Checks https://claude.dev/terminal/ every 5 minutes (GitHub Actions) and sends a phone push
via [ntfy](https://ntfy.sh) when the free Clawd plushies / Claude Code stickers come back,
or when a new swag item appears.

- Stock signal: `https://claude.dev/terminal/swag-status.json` (`{"off": [...]}`), plus the
  Brilliant redemption forms (which redirect to `/sorry` while closed).
- `state.json` holds the last known state so it only alerts on changes.
- The ntfy topic is stored in the `NTFY_TOPIC` repo secret.
- Test: Actions → plushie-watch → Run workflow → tick "Send a test push".
