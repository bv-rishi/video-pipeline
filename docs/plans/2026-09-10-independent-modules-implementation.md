# Independent modules implementation plan

1. Add a shared, versioned agent task/result contract and generic command adapter surface.
2. Move review-specific agent configuration and provider code under `modules/draft_review`.
3. Reduce shared `Settings` to local core/relay values plus opaque per-module configuration.
4. Add `none` agent behavior that preserves deterministic artifacts and reports an incomplete semantic stage.
5. Add independent `video-draft-review` and `video-conformer` entry points plus umbrella module discovery.
6. Add a conformer module boundary and sanitized SSL/domain benchmark summary without media or private paths.
7. Update documentation and example configuration with generic agent names and legacy aliases.
8. Add module-isolation, configuration, command-contract and CLI tests; run the full suite.
9. Bump the package patch version, commit and push to the public GitHub repository.
