# Private notification relay

The relay accepts small status events from editor Macs and posts them into one Google Chat space. Run one copy on an always-on private machine or small hosted service that can reach Google Chat.

Do not place the Google Chat webhook on all editor Macs. Keeping it only on the relay means one leaked or retired laptop cannot post directly to the group, and the webhook can be rotated in one place.

## 1. Create the Google Chat webhook

In the target Google Chat space:

1. Open the space menu.
2. Choose **Apps & integrations**, then **Add webhooks**.
3. Name it `Video Pipeline` and copy the generated URL once.

If the webhook option is unavailable, a Google Workspace administrator must allow incoming webhooks. Treat the URL as a password: never paste it into GitHub, a batch manifest, or a report.

## 2. Get the real mention IDs

Google Chat webhooks create an actual user tag with `<users/USER_ID>`, where `USER_ID` is the user's stable numeric Google Workspace ID—not their email address. A Workspace administrator can retrieve the `id` field with the Admin SDK Directory API for each team member. Put those IDs only in the relay's private config.

Create a private configuration file outside this public repository:

```json
{
  "reviewer_user_id": "123456789012345678901",
  "reviewer_label": "final reviewer",
  "editors": {
    "editor-one": "111111111111111111111",
    "editor-two": "222222222222222222222",
    "editor-three": "333333333333333333333"
  }
}
```

## 3. Configure and run the relay

Set secrets in the relay process:

```bash
export VIDEO_PIPELINE_RELAY_TOKENS_JSON='{"editor-one":"token-one","editor-two":"token-two","editor-three":"token-three"}'
export VIDEO_PIPELINE_CHAT_WEBHOOK_URL="the-private-webhook-url"
video-pipeline relay \
  --host 127.0.0.1 \
  --port 8787 \
  --db /private/path/relay-events.sqlite3 \
  --config /private/path/relay-config.json
```

The process needs a stable HTTPS address such as `https://video-pipeline-relay.example/events`. The simplest deployment is the Python relay on an existing always-on company server behind Caddy, nginx, or the company's normal HTTPS proxy. If there is no suitable server, a small managed relay can replace this Python process later; the editor-facing event format does not change.

## 4. Configure each editor Mac

On each editor Mac, set only the relay address and client token:

```bash
export VIDEO_PIPELINE_RELAY_URL="https://private-relay.example/events"
export VIDEO_PIPELINE_RELAY_TOKEN="this-editor's-own-token"
```

Each editor gets a different token, so it can be revoked without interrupting the others. The Google Chat webhook URL stays on the relay and must never be copied to editor machines or committed to GitHub.

## 5. Perform one bounded test

First use a temporary Chat space if available. Send one metadata-only event and verify that both the final reviewer and the submitting editor receive real notifications. Then run one mock batch and confirm that a repeated event is shown only once. After this passes, point the relay at the production Video Boys space.

The relay accepts only batch ID, editor key, counts, state, and event time. It rejects unknown event types, authenticates the submitting editor, deduplicates retries in SQLite, and never accepts videos, scripts, transcripts, screenshots, or reports.
