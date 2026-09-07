class FakeGmailClient:
    """Records calls and returns canned data for MCP dispatch tests."""

    def __init__(self, **canned):
        self.calls = []
        self.canned = canned

    def _record(self, _name, _default=None, **kwargs):
        self.calls.append((_name, kwargs))
        return self.canned.get(_name, _default)

    def count(self, query):
        return self._record("count", 0, query=query)

    def search_ids(self, query, limit=None):
        return self._record("search_ids", [], query=query, limit=limit)

    def metadata(self, ids):
        return self._record("metadata", [], ids=ids)

    def sender_stats(self, query, limit=None):
        return self._record("sender_stats", [], query=query, limit=limit)

    def trash_ids(self, ids):
        return self._record("trash_ids", len(ids), ids=ids)

    def mark_read_ids(self, ids):
        return self._record("mark_read_ids", len(ids), ids=ids)

    def mark_unread_ids(self, ids):
        return self._record("mark_unread_ids", len(ids), ids=ids)

    def modify_labels_ids(self, ids, add, remove):
        return self._record("modify_labels_ids", len(ids),
                            ids=ids, add=add, remove=remove)

    def list_labels(self):
        return self._record("list_labels", [])

    def create_label(self, name):
        return self._record("create_label", {"id": "L1", "name": name}, name=name)

    def update_label(self, label_id, name):
        return self._record("update_label", {"id": label_id, "name": name},
                            label_id=label_id, name=name)

    def delete_label(self, label_id):
        return self._record("delete_label", {"deleted": label_id}, label_id=label_id)

    def list_filters(self):
        return self._record("list_filters", [])

    def create_filter(self, criteria, action):
        return self._record("create_filter", {"id": "F1"},
                            criteria=criteria, action=action)

    def delete_filter(self, filter_id):
        return self._record("delete_filter", {"deleted": filter_id}, filter_id=filter_id)

    def get_message(self, message_id):
        return self._record("get_message", None, message_id=message_id)


class ErrorClient:
    def count(self, query):
        raise Exception("boom")
