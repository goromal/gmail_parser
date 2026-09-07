#!/usr/bin/env python3
# gmail MCP Server - gives Claude Code (and Codex) triage + bulk control over a
# Gmail account. Stdlib stdio JSON-RPC (mirrors folio-mcp-server.py); the actual
# Gmail work is delegated to gmail_parser.GMailCorpus, which already owns auth,
# fast metadata fetches, batched bulk actions, and label/filter management.
#
# Design: handle_tool_call() takes a duck-typed client so the dispatch layer is
# unit-tested against a fake with no network. The real GmailClient wraps
# GMailCorpus and is only constructed in main().
import sys
import json
import os


class GmailClient:
    """Thin adapter from MCP tool calls to a gmail_parser GMailCorpus."""

    def __init__(self, address, secrets_json, refresh_file):
        # Imported lazily so the module (and its tests) load without gmail_parser
        # and without triggering Google auth.
        from gmail_parser.corpus import GMailCorpus

        self.corpus = GMailCorpus(
            address,
            gmail_secrets_json=secrets_json,
            gmail_refresh_file=refresh_file,
            headless=True,
        )

    def count(self, query):
        return self.corpus.countMessages(query)

    def search_ids(self, query, limit=None):
        return self.corpus.searchMessageIds(query, limit=limit)

    def metadata(self, ids):
        return self.corpus.getMetadata(ids)

    def sender_stats(self, query, limit=None):
        return self.corpus.senderStats(query, limit=limit)

    def trash_ids(self, ids):
        return self.corpus.bulkTrash(ids)

    def mark_read_ids(self, ids):
        return self.corpus.bulkMarkRead(ids)

    def mark_unread_ids(self, ids):
        return self.corpus.bulkMarkUnread(ids)

    def modify_labels_ids(self, ids, add, remove):
        return self.corpus.bulkModifyLabels(ids, add_labels=add, remove_labels=remove)

    def list_labels(self):
        return self.corpus.getLabels()

    def create_label(self, name):
        return self.corpus.createLabel(name)

    def update_label(self, label_id, name):
        return self.corpus.updateLabel(label_id, name=name)

    def delete_label(self, label_id):
        return self.corpus.deleteLabel(label_id)

    def list_filters(self):
        return self.corpus.listFilters()

    def create_filter(self, criteria, action):
        return self.corpus.createFilter(criteria, action)

    def delete_filter(self, filter_id):
        return self.corpus.deleteFilter(filter_id)

    def get_message(self, message_id):
        message = self.corpus.getMessageById(message_id)
        if message is None:
            return None
        date = message.getDate()
        return {
            "id": message.getId(),
            "from": message.getSenderEmail(),
            "sender_name": message.getSenderName(),
            "subject": message.getSubject(),
            "date": date.isoformat() if hasattr(date, "isoformat") else str(date),
            "labels": message.getLabels(),
            "text": message.getText(),
        }


def _select_ids(client, args):
    """Resolve the set of message ids a bulk tool should act on.

    Accepts an explicit ``ids`` list, or a Gmail ``query`` that is expanded to
    ids (bounded by ``limit`` if given). Returns ``(ids, error)``; ``error`` is a
    message string when neither was usable, so a bulk action never runs against
    the whole mailbox by accident.
    """
    ids = args.get("ids")
    if ids:
        return list(ids), None
    query = args.get("query")
    if query:
        return client.search_ids(query, args.get("limit")), None
    return [], "provide either 'query' or 'ids'"


def handle_tool_call(client, name, args):
    """Dispatch an MCP tool call to the client. Returns JSON-serializable data."""
    try:
        if name == "gmail_count":
            query = args["query"]
            return {"query": query, "count": client.count(query)}
        elif name == "gmail_search":
            query = args["query"]
            limit = args.get("limit", 25)
            ids = client.search_ids(query, limit)
            return {"query": query, "returned": len(ids),
                    "messages": client.metadata(ids)}
        elif name == "gmail_sender_stats":
            query = args.get("query", "is:unread")
            return {"query": query,
                    "senders": client.sender_stats(query, args.get("limit"))}
        elif name == "gmail_trash":
            ids, error = _select_ids(client, args)
            if error:
                return {"error": error}
            requested = len(ids)
            trashed = client.trash_ids(ids) if ids else 0
            result = {"trashed": trashed, "requested": requested}
            if trashed < requested:
                # bulkTrash returns the count actually trashed; a shortfall
                # (e.g. rate-limited items that exhausted retries) is reported
                # explicitly rather than masquerading as full success.
                result["incomplete"] = requested - trashed
            return result
        elif name == "gmail_mark_read":
            ids, error = _select_ids(client, args)
            if error:
                return {"error": error}
            return {"marked_read": client.mark_read_ids(ids) if ids else 0}
        elif name == "gmail_mark_unread":
            ids, error = _select_ids(client, args)
            if error:
                return {"error": error}
            return {"marked_unread": client.mark_unread_ids(ids) if ids else 0}
        elif name == "gmail_modify_labels":
            ids, error = _select_ids(client, args)
            if error:
                return {"error": error}
            add = args.get("add_labels", [])
            remove = args.get("remove_labels", [])
            if not add and not remove:
                return {"error": "provide 'add_labels' and/or 'remove_labels'"}
            modified = client.modify_labels_ids(ids, add, remove) if ids else 0
            return {"modified": modified, "add_labels": add, "remove_labels": remove}
        elif name == "gmail_get_message":
            message = client.get_message(args["message_id"])
            return message if message is not None else {"error": "message not found"}
        elif name == "gmail_list_labels":
            return {"labels": client.list_labels()}
        elif name == "gmail_create_label":
            return client.create_label(args["name"])
        elif name == "gmail_update_label":
            return client.update_label(args["label_id"], args["name"])
        elif name == "gmail_delete_label":
            return client.delete_label(args["label_id"])
        elif name == "gmail_list_filters":
            return {"filters": client.list_filters()}
        elif name == "gmail_create_filter":
            return client.create_filter(args["criteria"], args["action"])
        elif name == "gmail_delete_filter":
            return client.delete_filter(args["filter_id"])
        else:
            return {"error": f"Unknown tool: {name}"}
    except Exception as e:
        return {"error": str(e)}


_QUERY_HELP = (
    "Gmail search query (the same `q` you'd type in the Gmail search box: "
    "from:, to:, subject:, is:unread, label:, newer_than:7d, has:attachment, "
    "and free text which searches message bodies)."
)

_SELECTOR_PROPS = {
    "query": {"type": "string", "description": _QUERY_HELP},
    "ids": {"type": "array", "items": {"type": "string"},
            "description": "Explicit message ids (from gmail_search) instead of a query."},
    "limit": {"type": "integer",
              "description": "When selecting by query, cap the number of matches acted on."},
}

TOOLS = [
    {"name": "gmail_count",
     "description": "Count messages matching a query, fast (ids only, no bodies). "
                    "e.g. query 'from:tiktok' to count how many TikTok sent.",
     "inputSchema": {"type": "object",
                     "properties": {"query": {"type": "string", "description": _QUERY_HELP}},
                     "required": ["query"]}},
    {"name": "gmail_search",
     "description": "List messages matching a query with lightweight metadata "
                    "(id, sender, subject, date, labels) - no bodies. Use the "
                    "returned ids with the bulk tools or gmail_get_message.",
     "inputSchema": {"type": "object",
                     "properties": {
                         "query": {"type": "string", "description": _QUERY_HELP},
                         "limit": {"type": "integer",
                                   "description": "Max messages to return (default 25)."}},
                     "required": ["query"]}},
    {"name": "gmail_sender_stats",
     "description": "Rank senders by how many messages they account for within a "
                    "query, most first. Defaults to query 'is:unread' - i.e. which "
                    "senders make up the most unread mail. Fetches metadata only.",
     "inputSchema": {"type": "object",
                     "properties": {
                         "query": {"type": "string",
                                   "description": _QUERY_HELP + " Defaults to 'is:unread'."},
                         "limit": {"type": "integer",
                                   "description": "Cap messages sampled (most recent). "
                                                  "Omit to count every match (slower on big mailboxes)."}}}},
    {"name": "gmail_trash",
     "description": "Move messages to Trash (recoverable for 30 days; this is a "
                    "normal Gmail delete, not permanent erasure). Select by query "
                    "or explicit ids. Consider gmail_count first to confirm the "
                    "blast radius before trashing by query.",
     "inputSchema": {"type": "object", "properties": dict(_SELECTOR_PROPS)}},
    {"name": "gmail_mark_read",
     "description": "Mark messages as read. Select by query or explicit ids.",
     "inputSchema": {"type": "object", "properties": dict(_SELECTOR_PROPS)}},
    {"name": "gmail_mark_unread",
     "description": "Mark messages as unread. Select by query or explicit ids.",
     "inputSchema": {"type": "object", "properties": dict(_SELECTOR_PROPS)}},
    {"name": "gmail_modify_labels",
     "description": "Add and/or remove labels on messages selected by query or "
                    "ids. Labels may be given by name (resolved automatically) or "
                    "id. System labels like INBOX can be removed to archive.",
     "inputSchema": {"type": "object",
                     "properties": dict(_SELECTOR_PROPS, **{
                         "add_labels": {"type": "array", "items": {"type": "string"},
                                        "description": "Label names or ids to add."},
                         "remove_labels": {"type": "array", "items": {"type": "string"},
                                           "description": "Label names or ids to remove."}})}},
    {"name": "gmail_get_message",
     "description": "Fetch one full message (body as plain text) by id. Slow path - "
                    "use after triaging with gmail_search/gmail_sender_stats.",
     "inputSchema": {"type": "object",
                     "properties": {"message_id": {"type": "string"}},
                     "required": ["message_id"]}},
    {"name": "gmail_list_labels",
     "description": "List all labels (id, name, type, visibility).",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "gmail_create_label",
     "description": "Create a new user label.",
     "inputSchema": {"type": "object",
                     "properties": {"name": {"type": "string"}},
                     "required": ["name"]}},
    {"name": "gmail_update_label",
     "description": "Rename a label (by its id, from gmail_list_labels).",
     "inputSchema": {"type": "object",
                     "properties": {"label_id": {"type": "string"},
                                    "name": {"type": "string"}},
                     "required": ["label_id", "name"]}},
    {"name": "gmail_delete_label",
     "description": "Delete a user label by id (messages are kept, just lose it).",
     "inputSchema": {"type": "object",
                     "properties": {"label_id": {"type": "string"}},
                     "required": ["label_id"]}},
    {"name": "gmail_list_filters",
     "description": "List mail filters (each with a criteria and an action).",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "gmail_create_filter",
     "description": "Create a filter. 'criteria' is a Gmail filter criteria object "
                    "(e.g. {\"from\": \"news@x.com\"} or {\"query\": \"subject:sale\"}); "
                    "'action' is an action object (e.g. {\"addLabelIds\": [\"Label_5\"], "
                    "\"removeLabelIds\": [\"INBOX\", \"UNREAD\"]}). Use gmail_list_labels "
                    "for label ids.",
     "inputSchema": {"type": "object",
                     "properties": {"criteria": {"type": "object"},
                                    "action": {"type": "object"}},
                     "required": ["criteria", "action"]}},
    {"name": "gmail_delete_filter",
     "description": "Delete a filter by id (from gmail_list_filters).",
     "inputSchema": {"type": "object",
                     "properties": {"filter_id": {"type": "string"}},
                     "required": ["filter_id"]}},
]


def handle_request(client, request):
    method = request.get("method")
    req_id = request.get("id")
    if method == "initialize":
        result = {"protocolVersion": "2024-11-05",
                  "capabilities": {"tools": {}},
                  "serverInfo": {"name": "gmail-mcp-server", "version": "1.0.0"}}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = request.get("params", {})
        tool_result = handle_tool_call(client, params.get("name"),
                                       params.get("arguments", {}))
        result = {"content": [{"type": "text", "text": json.dumps(tool_result)}]}
    else:
        return {"jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def main():
    address = os.environ.get("GMAIL_ADDRESS", "andrew.torgesen@gmail.com")
    secrets_json = os.environ.get(
        "GMAIL_SECRETS_JSON", "~/secrets/google/client_secrets.json"
    )
    refresh_file = os.environ.get("GMAIL_REFRESH_FILE", "~/secrets/google/refresh.json")

    # gmail_parser's callAPI (and progressbar) write diagnostics to stdout; on a
    # stdio server that would corrupt the JSON-RPC framing. Keep the real stdout
    # for protocol writes only and point every other stdout write at stderr.
    protocol_out = sys.stdout
    sys.stdout = sys.stderr

    client = GmailClient(address, secrets_json, refresh_file)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "id" not in request:  # notification - no response
            continue
        response = handle_request(client, request)
        protocol_out.write(json.dumps(response) + "\n")
        protocol_out.flush()


if __name__ == "__main__":
    main()
