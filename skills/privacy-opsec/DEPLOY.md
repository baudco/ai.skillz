# Privacy Opsec Deployment

`privacy-opsec` is a generic, provider-neutral skill with no required local
assets or dependent skills.

Deploy it to a repository for both supported providers:

```console
bash /path/to/ai.skillz/scripts/deploy.sh privacy-opsec /path/to/repo \
  --provider all
```

The skill can reason without privileged tools. Implementing or verifying its
Linux network controls may require `iproute2`, nftables, WireGuard tooling,
packet/socket inspection, and authorization to inspect the target host.

Restart the AI harness after deployment so its skill discovery is refreshed.
