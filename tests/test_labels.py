from gmail_parser.labels import label_map_from_list_response


def test_maps_name_to_id():
    resp = {"labels": [
        {"id": "Label_1", "name": "Newsletters"},
        {"id": "INBOX", "name": "INBOX"},
    ]}
    assert label_map_from_list_response(resp) == {
        "Newsletters": "Label_1",
        "INBOX": "INBOX",
    }


def test_empty_response_yields_empty_map():
    assert label_map_from_list_response({}) == {}
