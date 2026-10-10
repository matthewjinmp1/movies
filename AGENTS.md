# Project preferences

- After completing and verifying requested changes, commit and push them to the configured GitHub remote. The user has requested automatic pushes; do not ask for confirmation each time.
- Keep IMDb downloads, generated datasets/databases, and personal settings out of Git. Respect `.gitignore` and inspect the staged files before committing.
- Never force-push or overwrite unrelated changes to satisfy the automatic-push preference.
- After each change is finished and verified, restart the local movie server on port 3002 with `./run_server.command --no-browser` so the user gets the change automatically. Do not restart mid-edit, while the app may be broken.
