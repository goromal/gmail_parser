import unittest

import gmail_mcp_server as srv
from tests.fakes import FakeGmailClient, ErrorClient


class TriageToolTest(unittest.TestCase):
    def test_count(self):
        c = FakeGmailClient(count=17)
        out = srv.handle_tool_call(c, "gmail_count", {"query": "from:tiktok"})
        self.assertEqual(out, {"query": "from:tiktok", "count": 17})
        self.assertEqual(c.calls[0], ("count", {"query": "from:tiktok"}))

    def test_search_returns_metadata_for_matched_ids(self):
        c = FakeGmailClient(search_ids=["a", "b"],
                            metadata=[{"id": "a"}, {"id": "b"}])
        out = srv.handle_tool_call(c, "gmail_search", {"query": "x", "limit": 5})
        self.assertEqual(out["returned"], 2)
        self.assertEqual(out["messages"], [{"id": "a"}, {"id": "b"}])
        self.assertEqual(c.calls[0], ("search_ids", {"query": "x", "limit": 5}))
        self.assertEqual(c.calls[1], ("metadata", {"ids": ["a", "b"]}))

    def test_search_default_limit(self):
        c = FakeGmailClient()
        srv.handle_tool_call(c, "gmail_search", {"query": "x"})
        self.assertEqual(c.calls[0], ("search_ids", {"query": "x", "limit": 25}))

    def test_sender_stats_defaults_to_unread(self):
        c = FakeGmailClient(sender_stats=[{"sender": "a", "count": 3}])
        out = srv.handle_tool_call(c, "gmail_sender_stats", {})
        self.assertEqual(out["query"], "is:unread")
        self.assertEqual(out["senders"], [{"sender": "a", "count": 3}])
        self.assertEqual(c.calls[0], ("sender_stats", {"query": "is:unread", "limit": None}))

    def test_sender_stats_custom_query_and_limit(self):
        c = FakeGmailClient()
        srv.handle_tool_call(c, "gmail_sender_stats", {"query": "label:promos", "limit": 100})
        self.assertEqual(c.calls[0],
                         ("sender_stats", {"query": "label:promos", "limit": 100}))


class BulkSelectorTest(unittest.TestCase):
    def test_trash_by_query_expands_ids(self):
        c = FakeGmailClient(search_ids=["1", "2", "3"])
        out = srv.handle_tool_call(c, "gmail_trash", {"query": "from:tiktok"})
        self.assertEqual(out, {"trashed": 3})
        self.assertEqual(c.calls[0], ("search_ids", {"query": "from:tiktok", "limit": None}))
        self.assertEqual(c.calls[1], ("trash_ids", {"ids": ["1", "2", "3"]}))

    def test_trash_by_explicit_ids_skips_search(self):
        c = FakeGmailClient()
        out = srv.handle_tool_call(c, "gmail_trash", {"ids": ["x", "y"]})
        self.assertEqual(out, {"trashed": 2})
        self.assertEqual(c.calls, [("trash_ids", {"ids": ["x", "y"]})])

    def test_trash_without_selector_errors_and_acts_on_nothing(self):
        c = FakeGmailClient()
        out = srv.handle_tool_call(c, "gmail_trash", {})
        self.assertIn("error", out)
        self.assertEqual(c.calls, [])

    def test_trash_query_matching_nothing_trashes_nothing(self):
        c = FakeGmailClient(search_ids=[])
        out = srv.handle_tool_call(c, "gmail_trash", {"query": "from:nobody"})
        self.assertEqual(out, {"trashed": 0})
        self.assertEqual([call[0] for call in c.calls], ["search_ids"])

    def test_mark_read(self):
        c = FakeGmailClient()
        out = srv.handle_tool_call(c, "gmail_mark_read", {"ids": ["a"]})
        self.assertEqual(out, {"marked_read": 1})

    def test_mark_unread(self):
        c = FakeGmailClient()
        out = srv.handle_tool_call(c, "gmail_mark_unread", {"ids": ["a", "b"]})
        self.assertEqual(out, {"marked_unread": 2})

    def test_modify_labels_passthrough(self):
        c = FakeGmailClient()
        out = srv.handle_tool_call(c, "gmail_modify_labels", {
            "ids": ["a"], "add_labels": ["Receipts"], "remove_labels": ["INBOX"]})
        self.assertEqual(out["modified"], 1)
        self.assertEqual(c.calls[0],
                         ("modify_labels_ids",
                          {"ids": ["a"], "add": ["Receipts"], "remove": ["INBOX"]}))

    def test_modify_labels_requires_a_label_change(self):
        c = FakeGmailClient()
        out = srv.handle_tool_call(c, "gmail_modify_labels", {"ids": ["a"]})
        self.assertIn("error", out)
        self.assertEqual(c.calls, [])


class ManagementToolTest(unittest.TestCase):
    def test_get_message_found(self):
        c = FakeGmailClient(get_message={"id": "m1", "text": "hi"})
        out = srv.handle_tool_call(c, "gmail_get_message", {"message_id": "m1"})
        self.assertEqual(out, {"id": "m1", "text": "hi"})

    def test_get_message_missing(self):
        c = FakeGmailClient(get_message=None)
        out = srv.handle_tool_call(c, "gmail_get_message", {"message_id": "nope"})
        self.assertIn("error", out)

    def test_list_labels(self):
        c = FakeGmailClient(list_labels=[{"id": "L1", "name": "A"}])
        out = srv.handle_tool_call(c, "gmail_list_labels", {})
        self.assertEqual(out, {"labels": [{"id": "L1", "name": "A"}]})

    def test_create_label(self):
        c = FakeGmailClient()
        out = srv.handle_tool_call(c, "gmail_create_label", {"name": "Newsletters"})
        self.assertEqual(out["name"], "Newsletters")
        self.assertEqual(c.calls[0], ("create_label", {"name": "Newsletters"}))

    def test_update_label(self):
        c = FakeGmailClient()
        srv.handle_tool_call(c, "gmail_update_label", {"label_id": "L2", "name": "New"})
        self.assertEqual(c.calls[0], ("update_label", {"label_id": "L2", "name": "New"}))

    def test_delete_label(self):
        c = FakeGmailClient()
        out = srv.handle_tool_call(c, "gmail_delete_label", {"label_id": "L3"})
        self.assertEqual(out, {"deleted": "L3"})

    def test_list_filters(self):
        c = FakeGmailClient(list_filters=[{"id": "F1"}])
        out = srv.handle_tool_call(c, "gmail_list_filters", {})
        self.assertEqual(out, {"filters": [{"id": "F1"}]})

    def test_create_filter(self):
        c = FakeGmailClient()
        criteria = {"from": "news@x.com"}
        action = {"addLabelIds": ["L1"], "removeLabelIds": ["INBOX"]}
        srv.handle_tool_call(c, "gmail_create_filter",
                             {"criteria": criteria, "action": action})
        self.assertEqual(c.calls[0],
                         ("create_filter", {"criteria": criteria, "action": action}))

    def test_delete_filter(self):
        c = FakeGmailClient()
        out = srv.handle_tool_call(c, "gmail_delete_filter", {"filter_id": "F9"})
        self.assertEqual(out, {"deleted": "F9"})


class ErrorHandlingTest(unittest.TestCase):
    def test_unknown_tool(self):
        out = srv.handle_tool_call(FakeGmailClient(), "gmail_bogus", {})
        self.assertIn("error", out)

    def test_client_exception_becomes_error(self):
        out = srv.handle_tool_call(ErrorClient(), "gmail_count", {"query": "x"})
        self.assertEqual(out, {"error": "boom"})

    def test_missing_required_arg_becomes_error(self):
        out = srv.handle_tool_call(FakeGmailClient(), "gmail_count", {})
        self.assertIn("error", out)


if __name__ == "__main__":
    unittest.main()
