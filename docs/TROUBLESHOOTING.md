# Troubleshooting

## Common failures

### “Missing required secret file env var”
Ensure `bws-fetch` is running and the wrapper repo supplies
`BWS_ACCESS_TOKEN` and `BWS_PROJECT_ID`.

### “Event … is not allowed”
Check `configs/event-allowlist.json` and confirm the wrapper workflow
passes `event-name` and `expected-event-action` correctly.

### “Target org … is not in installation mapping”
Verify `GH_INSTALL_JSON` includes the org and is current in BWS.

### “Invalid repo_full_name”
Ensure payloads use the format `<org>/<repo>` with valid characters only.

### “Checksum mismatch for bws”
Update `BWS_VERSION`/`BWS_SHA256` to the correct release values.
