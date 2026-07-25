"""Gmail label helpers.

Rules reference labels by their user-facing NAME, but the Gmail API tags
messages with label IDs. This converts a ``users().labels().list()`` response
into the name -> id map the processor needs.
"""


def label_map_from_list_response(response):
    """Build a ``{name: id}`` map from a labels().list() API response."""
    return {label["name"]: label["id"] for label in response.get("labels", [])}
