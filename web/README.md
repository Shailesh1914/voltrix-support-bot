Web interface for the support bot (spec 08 section 4). It only wraps
the query flow in `query/flow.py`. It never changes what the bot decides.

Run it on the laptop, from the project root:

    python -m web

This listens on http://0.0.0.0:8080 with uvicorn's access log off. Use
`python -m web` rather than the `uvicorn` command: it turns the access
log off and stops with a one-line error if a setting is wrong.

Files:
- `app.py`: the three endpoints `GET /`, `GET /health` and `POST /ask`.
- `page.html`: the one HTML page, with no external scripts or fonts.
- `secret_source.py`: where the Anthropic key and the access code come
  from (`VOLTRIX_SECRETS_SOURCE`, spec 08 section 5).
- `startup.py`: builds the app once, through `query.ask.build_flow()`.
- `__main__.py`: `python -m web`.

Settings (spec 08 section 5):
- `VOLTRIX_SECRETS_SOURCE`: `file` (default) or `parameter_store`.
- File mode: `VOLTRIX_ANTHROPIC_API_KEY` and `VOLTRIX_ACCESS_CODE` are read
  from `~/.config/voltrix/secrets.env`, where `~` is the home folder of
  the user the app runs as. In the container, mount the file there
  read-only.
- Parameter Store mode: `/voltrix/anthropic-key` and `/voltrix/access-code`
  (SecureString). They are read once at start-up.
- `IMAGE_TAG` (optional): shown by `/health`. Default: `local`.
- `HANDOFF_DIR` (optional): records go to `<HANDOFF_DIR>/handoffs.jsonl`.
  Do not set it together with `HANDOFF_PATH`.
- The access code must be at least 12 characters. Any variable starting
  with `ANTHROPIC_` stops the start-up.
