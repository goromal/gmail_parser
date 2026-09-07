import unittest

import gmail_mcp_server as srv
from tests.fakes import FakeGmailClient

EXPECTED_TOOLS = {
    "gmail_count", "gmail_search", "gmail_sender_stats", "gmail_trash",
    "gmail_mark_read", "gmail_mark_unread", "gmail_modify_labels",
    "gmail_get_message", "gmail_list_labels", "gmail_create_label",
    "gmail_update_label", "gmail_delete_label", "gmail_list_filters",
    "gmail_create_filter", "gmail_delete_filter",
}


class ProtocolTest(unittest.TestCase):
    def test_tools_list_advertises_all(self):
        resp = srv.handle_request(FakeGmailClient(),
                                  {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        names = {t["name"] for t in resp["result"]["tools"]}
        self.assertEqual(names, EXPECTED_TOOLS)
        for t in resp["result"]["tools"]:
            self.assertIn("inputSchema", t)

    def test_initialize(self):
        resp = srv.handle_request(FakeGmailClient(),
                                  {"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        self.assertEqual(resp["result"]["serverInfo"]["name"], "gmail-mcp-server")

    def test_tools_call_wraps_result(self):
        c = FakeGmailClient(count=42)
        resp = srv.handle_request(c, {
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "gmail_count", "arguments": {"query": "from:tiktok"}}})
        content = resp["result"]["content"][0]
        self.assertEqual(content["type"], "text")
        self.assertIn('"count": 42', content["text"])

    def test_unknown_method(self):
        resp = srv.handle_request(FakeGmailClient(),
                                  {"jsonrpc": "2.0", "id": 3, "method": "bogus"})
        self.assertIn("error", resp)
        self.assertEqual(resp["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main()
