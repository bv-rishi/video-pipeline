# Private notification relay

The relay accepts small status events from editor Macs and posts them into one Google Chat space. Run it on a private machine or small hosted service that can reach Google Chat.

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

Set secrets in the relay process:

```bash
export VIDEO_PIPELINE_RELAY_TOKENS_JSON='{"editor-one":"token-one","editor-two":"token-two","editor-three":"token-three"}'
export VIDEO_PIPELINE_CHAT_WEBHOOK_URL="the-private-webhook-url"
video-pipeline relay --config /private/path/relay-config.json
```

On each editor Mac, set only the relay address and client token:

```bash
export VIDEO_PIPELINE_RELAY_URL="https://private-relay.example/events"
export VIDEO_PIPELINE_RELAY_TOKEN="this-editor's-own-token"
```

Each editor gets a different token, so it can be revoked without interrupting the others. The Google Chat webhook URL stays on the relay and must never be copied to editor machines or committed to GitHub.

The relay formats real mentions using Google's `<users/USER_ID>` syntax. Workspace administrators must allow incoming webhooks in the target space.
