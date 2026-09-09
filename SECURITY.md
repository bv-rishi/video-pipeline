# Security policy

Do not report credential exposure through a public GitHub issue. Contact the repository maintainers privately and revoke the exposed credential immediately.

Never commit:

- GLM or other model API keys;
- Google Chat webhook URLs or relay tokens;
- real videos, audio, scripts, screenshots, transcripts, or reports;
- Google Chat user IDs or private group information.

The relay should use HTTPS when it is reachable outside a private network. Give each editor a revocable client token in a production deployment. Store local credentials in macOS Keychain, the process environment, or a private configuration outside the repository.
