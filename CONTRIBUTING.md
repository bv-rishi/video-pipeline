# Contributing

Thank you for improving Video Pipeline.

## Propose a change

1. Fork the public repository or create a short-lived branch.
2. Keep one pull request focused on one module or one shared-core change.
3. Add or update tests.
4. Explain whether the change affects one video, one module, or the whole pipeline.
5. Confirm that fixtures contain no real production media, scripts, reports, identities, or credentials.

Run the tests before opening the pull request:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Changes to shared contracts require a compatibility note. Changes to review prompts or rules require a sanitized example showing the missed issue or false positive that motivated the change.

## Editorial feedback

Production feedback should first be recorded privately. Convert it into a sanitized regression fixture before proposing a public rule change. Never paste a real video frame, transcript, email address, temporary site URL, customer detail, or unpublished script into a public issue.
