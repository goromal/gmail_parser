# gmail-mcp

MCP server giving Claude Code (and Codex) triage and bulk control over a Gmail
account. Stdlib-only stdio JSON-RPC (mirrors `folio-mcp-server.py`); the Gmail
work is delegated to [`gmail_parser`](../README.md)'s `GMailCorpus`, which owns
auth, fast metadata fetches, batched bulk actions, and label/filter management.

## Config (environment)

- `GMAIL_ADDRESS` - account address (default `andrew.torgesen@gmail.com`).
- `GMAIL_SECRETS_JSON` - Google client secrets (default `~/secrets/google/client_secrets.json`).
- `GMAIL_REFRESH_FILE` - OAuth refresh token (default `~/secrets/google/refresh.json`).

The refresh token must carry the full-mailbox scope (`https://mail.google.com/`),
which `easy_google_auth` already grants - so read, modify, trash, label, and
filter operations all work with the existing credentials.

## Tools (all prefixed `gmail_`)

Fast triage (metadata / ids only, never downloads bodies):

- `count` - how many messages match a query (e.g. `from:tiktok`).
- `search` - matching messages with id/sender/subject/date/labels.
- `sender_stats` - senders ranked by volume within a query (default `is:unread`).

Bulk actions (select by `query` or explicit `ids`):

- `trash` - move to Trash (recoverable; a normal Gmail delete, not permanent).
- `mark_read` / `mark_unread`.
- `modify_labels` - add/remove labels (by name or id; remove `INBOX` to archive).

Reading and management:

- `get_message` - one full message body (slow path, by id).
- `list_labels`, `create_label`, `update_label`, `delete_label`.
- `list_filters`, `create_filter`, `delete_filter`.

Deletion is deliberately Trash-only: no permanent bulk-erase is exposed to the
agent. Prefer `count` before trashing by query to confirm the blast radius.

## Test

    cd mcp && python3 -m unittest discover -s tests -v
