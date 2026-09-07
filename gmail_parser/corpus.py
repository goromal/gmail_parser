import os
import sys
import logging
import time
from datetime import datetime
import progressbar
import base64
from email.mime.text import MIMEText

from easy_google_auth.auth import getGoogleService

from gmail_parser.utils import callAPI, GMailMessage
from gmail_parser.defaults import GmailParserDefaults as GPD


class GMailCorpus(object):
    def _check_valid_interface(func):
        def wrapper(self, *args, **kwargs):
            if self.service is None:
                raise Exception(
                    "GMail interface not initialized properly; check your secrets"
                )
            return func(self, *args, **kwargs)

        return wrapper

    def __init__(self, email_address, messages=None, **kwargs):
        self.gmail_secrets_json = GPD.getKwargsOrDefault("gmail_secrets_json", **kwargs)
        self.gmail_refresh_file = GPD.getKwargsOrDefault("gmail_refresh_file", **kwargs)
        self.enable_logging = GPD.getKwargsOrDefault("enable_logging", **kwargs)
        headless = kwargs["headless"] if "headless" in kwargs else False

        if self.enable_logging:
            logging.basicConfig(
                filename="LOG-google_tools_GMAIL_%s.log"
                % time.strftime("%Y%m%d-%H%M%S"),
                level=logging.INFO,
            )
            logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))

        self.service = None
        try:
            self.service = getGoogleService(
                "gmail",
                "v1",
                self.gmail_secrets_json,
                self.gmail_refresh_file,
                headless=headless,
            )
        except:
            pass

        self.userID = email_address

        if messages is None:
            self.messages = []
        else:
            self.messages = messages

    @_check_valid_interface
    def send(self, to, subject, message):
        msg = MIMEText(message)
        msg["to"] = to
        msg["subject"] = subject
        msg_obj = {"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()}
        callAPI(self.service.users().messages().send(userId=self.userID, body=msg_obj))

    @_check_valid_interface
    def __enter__(self):
        return self

    @_check_valid_interface
    def __exit__(self, exc_type, exc_value, traceback):
        self.service.close()

    @_check_valid_interface
    def _scoped_copy(self, messages):
        return GMailCorpus(
            self.userID,
            messages,
            gmail_secrets_json=self.gmail_secrets_json,
            gmail_refresh_file=self.gmail_refresh_file,
            enable_logging=self.enable_logging,
        )

    @_check_valid_interface
    def _log(self, msg):
        if self.enable_logging:
            logging.info("[GMAILCORPUS] " + msg)

    @_check_valid_interface
    def _logwarn(self, msg):
        if self.enable_logging:
            logging.warn("[GMAILCORPUS] " + msg)

    @_check_valid_interface
    def _get_all_mail(self, limit, label_ids=("INBOX",)):
        # label_ids=None lists the latest messages mailbox-wide (used by the
        # cleaner, which matches rules on each message's own labels); the
        # default keeps Inbox()/Outbox() scoped to INBOX as before.
        list_kwargs = {"userId": self.userID}
        if label_ids is not None:
            list_kwargs["labelIds"] = list(label_ids)
        json_messages = list()
        list_response = callAPI(
            self.service.users()
            .messages()
            .list(maxResults=limit, **list_kwargs)
        )
        self._log("Front Page -> %d messages." % len(list_response["messages"]))
        json_messages.extend(list_response["messages"])
        while "nextPageToken" in list_response and len(json_messages) < limit:
            page_token = list_response["nextPageToken"]
            list_response = callAPI(
                self.service.users()
                .messages()
                .list(
                    maxResults=limit - len(json_messages),
                    pageToken=page_token,
                    **list_kwargs,
                )
            )
            if "messages" in list_response:
                self._log(
                    "Page %s -> %d messages."
                    % (page_token, len(list_response["messages"]))
                )
                json_messages.extend(list_response["messages"])
        self._log("%d total messages." % len(json_messages))
        return json_messages

    @_check_valid_interface
    def Inbox(self, limit=50000, reporter=None):
        from gmail_parser.progress import ProgressReporter, STAGE_DOWNLOAD

        reporter = reporter or ProgressReporter(None)
        self._log("Constructing Inbox.")
        self.messages.clear()
        all_mail = self._get_all_mail(limit)
        total = len(all_mail)
        for i in progressbar.progressbar(range(total)):
            json_message = all_mail[i]
            thread_json_message = callAPI(
                self.service.users()
                .threads()
                .get(userId=self.userID, id=json_message["threadId"])
            )
            if "messages" in thread_json_message:
                thread_msgs_json = thread_json_message["messages"]
                if (
                    "labelIds" in thread_msgs_json[0]
                    and "INBOX" in thread_msgs_json[0]["labelIds"]
                ):
                    self.messages.append(GMailMessage(thread_msgs_json, self))
            else:
                self._logwarn("Received a thread with no messages.")
            reporter.emit(STAGE_DOWNLOAD, i + 1, total)
        self._log("%d total INBOX messages." % len(self.messages))
        self._log("%d -> %d messages." % (len(all_mail), len(self.messages)))
        return self

    @_check_valid_interface
    def loadRecent(self, limit, reporter=None):
        """Load the latest ``limit`` messages mailbox-wide (no INBOX filter),
        each as its own message so rules can match on its labels."""
        from gmail_parser.progress import ProgressReporter, STAGE_DOWNLOAD

        reporter = reporter or ProgressReporter(None)
        self._log("Loading %d most recent messages." % limit)
        self.messages.clear()
        all_mail = self._get_all_mail(limit, label_ids=None)
        total = len(all_mail)
        for i in progressbar.progressbar(range(total)):
            json_message = all_mail[i]
            full_json_message = callAPI(
                self.service.users()
                .messages()
                .get(userId=self.userID, id=json_message["id"])
            )
            if full_json_message:
                self.messages.append(GMailMessage([full_json_message], self))
            reporter.emit(STAGE_DOWNLOAD, i + 1, total)
        self._log("%d messages loaded." % len(self.messages))
        return self

    @_check_valid_interface
    def getLabelMap(self):
        """Return a ``{label name: label id}`` map from the account's labels."""
        from gmail_parser.labels import label_map_from_list_response

        return label_map_from_list_response(
            callAPI(self.service.users().labels().list(userId=self.userID))
        )

    @_check_valid_interface
    def getLabels(self):
        """Return the account's full label objects (id, name, type, ...).

        Unlike :meth:`getLabelMap` (name -> id only) this keeps every field, so
        callers can show label visibility/type or find the id to patch/delete.
        """
        response = callAPI(self.service.users().labels().list(userId=self.userID))
        return response.get("labels", [])

    @_check_valid_interface
    def _resolve_label_ids(self, labels):
        """Map a mix of label NAMES and ids to ids (names via the label map,
        unknown values - e.g. system labels like ``UNREAD`` - pass through)."""
        if not labels:
            return []
        name_to_id = self.getLabelMap()
        return [name_to_id.get(label, label) for label in labels]

    @_check_valid_interface
    def searchMessageIds(self, query, limit=None):
        """Return ids of messages matching a Gmail search ``query`` (the `q`
        operator: ``from:``, ``subject:``, ``is:unread``, ``label:``, free text
        that searches bodies, etc.).

        Pages through ``messages().list`` collecting only ids - no per-message
        fetch - so counting or selecting by sender/subject/content/label is
        fast. ``limit=None`` returns every match.
        """
        ids = []
        page_token = None
        while True:
            page_size = 500
            if limit is not None:
                remaining = limit - len(ids)
                if remaining <= 0:
                    break
                page_size = min(500, remaining)
            list_response = callAPI(
                self.service.users()
                .messages()
                .list(
                    userId=self.userID,
                    q=query,
                    maxResults=page_size,
                    pageToken=page_token,
                )
            )
            for message in list_response.get("messages", []):
                ids.append(message["id"])
            page_token = list_response.get("nextPageToken")
            if not page_token:
                break
        return ids

    @_check_valid_interface
    def countMessages(self, query):
        """Exact count of messages matching ``query`` (ids only, no bodies)."""
        return len(self.searchMessageIds(query))

    @_check_valid_interface
    def getMetadata(self, ids, reporter=None):
        """Fetch header-only metadata for ``ids`` in batches of 100.

        Uses ``get(format='metadata', metadataHeaders=['From','Subject'])`` so
        no bodies (or threads) are downloaded. Returns the dicts produced by
        :func:`gmail_parser.search.parse_metadata_message`.
        """
        from gmail_parser.search import parse_metadata_message, chunked
        from gmail_parser.progress import ProgressReporter, STAGE_DOWNLOAD

        reporter = reporter or ProgressReporter(None)
        metas = []
        total = len(ids)
        done = 0
        for batch_ids in chunked(list(ids), 100):
            results = {}

            def _cb(request_id, response, exception, _results=results):
                if exception is None and response is not None:
                    _results[request_id] = response

            batch = self.service.new_batch_http_request()
            for message_id in batch_ids:
                batch.add(
                    self.service.users()
                    .messages()
                    .get(
                        userId=self.userID,
                        id=message_id,
                        format="metadata",
                        metadataHeaders=["From", "Subject"],
                    ),
                    request_id=message_id,
                    callback=_cb,
                )
            try:
                batch.execute()
            except Exception as e:
                print(e)
            for message_id in batch_ids:
                if message_id in results:
                    metas.append(parse_metadata_message(results[message_id]))
                done += 1
                reporter.emit(STAGE_DOWNLOAD, done, total)
        return metas

    @_check_valid_interface
    def senderStats(self, query=None, limit=None, reporter=None):
        """Sender counts for messages matching ``query`` (default: all mail).

        ``senderStats("is:unread")`` answers "which senders account for the most
        unread mail?" cheaply - it fetches only metadata, never bodies. Returns
        the list from :func:`gmail_parser.search.aggregate_senders`.
        """
        from gmail_parser.search import aggregate_senders

        ids = self.searchMessageIds(query or "", limit=limit)
        metas = self.getMetadata(ids, reporter=reporter)
        return aggregate_senders(metas)

    @_check_valid_interface
    def bulkModifyLabels(self, ids, add_labels=(), remove_labels=()):
        """Add/remove labels on many messages via ``batchModify`` (<=1000 ids
        per call). ``add_labels``/``remove_labels`` accept label NAMES or ids.
        Returns the number of ids acted on.
        """
        from gmail_parser.search import chunked

        add_ids = self._resolve_label_ids(add_labels)
        remove_ids = self._resolve_label_ids(remove_labels)
        ids = list(ids)
        for chunk in chunked(ids, 1000):
            body = {
                "ids": chunk,
                "addLabelIds": add_ids,
                "removeLabelIds": remove_ids,
            }
            callAPI(
                self.service.users()
                .messages()
                .batchModify(userId=self.userID, body=body)
            )
        return len(ids)

    @_check_valid_interface
    def bulkMarkRead(self, ids):
        """Mark many messages read (remove the UNREAD label)."""
        return self.bulkModifyLabels(ids, remove_labels=["UNREAD"])

    @_check_valid_interface
    def bulkMarkUnread(self, ids):
        """Mark many messages unread (add the UNREAD label)."""
        return self.bulkModifyLabels(ids, add_labels=["UNREAD"])

    @_check_valid_interface
    def bulkTrash(self, ids, reporter=None, batch_size=50, max_attempts=6):
        """Move many messages to Trash (recoverable), returning the number
        ACTUALLY trashed.

        Trashing is deliberately used instead of ``batchDelete`` (which is
        permanent and unrecoverable): a mistaken bulk action can still be undone
        from Gmail's Trash for 30 days.

        Gmail rate-limits bursts of per-message ``trash`` calls (HTTP 429). Each
        batch is sent with a per-item callback so failures are seen (not silently
        dropped), and any failed ids are retried with exponential backoff. Trash
        is idempotent, so retrying an id that in fact succeeded is harmless;
        success is tracked in a set so such an id is never counted twice. A
        return value < ``len(ids)`` means some ids could not be trashed even
        after ``max_attempts`` - the caller should treat the difference as a
        real failure, not assume completion.
        """
        import time

        from gmail_parser.search import chunked
        from gmail_parser.progress import ProgressReporter, STAGE_APPLY

        reporter = reporter or ProgressReporter(None)
        ids = list(ids)
        total = len(ids)
        trashed_ids = set()

        for batch_ids in chunked(ids, batch_size):
            pending = list(batch_ids)
            attempt = 0
            while pending and attempt < max_attempts:
                failed = []

                def _cb(request_id, response, exception, _failed=failed):
                    if exception is not None:
                        _failed.append(request_id)

                batch = self.service.new_batch_http_request()
                for message_id in pending:
                    batch.add(
                        self.service.users()
                        .messages()
                        .trash(userId=self.userID, id=message_id),
                        request_id=message_id,
                        callback=_cb,
                    )
                try:
                    batch.execute()
                    failed_set = set(failed)
                except Exception as e:
                    print(e)
                    failed_set = set(pending)  # whole batch did not go through

                for message_id in pending:
                    if message_id not in failed_set:
                        trashed_ids.add(message_id)
                reporter.emit(STAGE_APPLY, len(trashed_ids), total)

                pending = list(failed_set)
                attempt += 1
                if pending:
                    time.sleep(min(0.5 * (2 ** attempt), 8.0))  # backoff on 429s

        return len(trashed_ids)

    @_check_valid_interface
    def getMessageById(self, message_id):
        """Fetch one full message (body included) as a ``GMailMessage``, or
        ``None`` if it cannot be retrieved. This is the slow, single-message
        path used once a metadata triage has picked a message worth reading."""
        full = callAPI(
            self.service.users().messages().get(userId=self.userID, id=message_id)
        )
        if not full:
            return None
        return GMailMessage([full], self)

    @_check_valid_interface
    def createLabel(
        self,
        name,
        label_list_visibility="labelShow",
        message_list_visibility="show",
    ):
        """Create a user label; returns the created label object."""
        body = {
            "name": name,
            "labelListVisibility": label_list_visibility,
            "messageListVisibility": message_list_visibility,
        }
        return callAPI(
            self.service.users().labels().create(userId=self.userID, body=body)
        )

    @_check_valid_interface
    def updateLabel(
        self,
        label_id,
        name=None,
        label_list_visibility=None,
        message_list_visibility=None,
    ):
        """Patch a label's name/visibility; returns the updated label object."""
        body = {"id": label_id}
        if name is not None:
            body["name"] = name
        if label_list_visibility is not None:
            body["labelListVisibility"] = label_list_visibility
        if message_list_visibility is not None:
            body["messageListVisibility"] = message_list_visibility
        return callAPI(
            self.service.users()
            .labels()
            .patch(userId=self.userID, id=label_id, body=body)
        )

    @_check_valid_interface
    def deleteLabel(self, label_id):
        """Delete a user label (messages keep, just lose the label)."""
        callAPI(
            self.service.users().labels().delete(userId=self.userID, id=label_id)
        )
        return {"deleted": label_id}

    @_check_valid_interface
    def listFilters(self):
        """Return the account's mail filters (criteria + action objects)."""
        response = callAPI(
            self.service.users().settings().filters().list(userId=self.userID)
        )
        return response.get("filter", [])

    @_check_valid_interface
    def createFilter(self, criteria, action):
        """Create a filter from a ``criteria`` dict (from/to/subject/query/...)
        and an ``action`` dict (addLabelIds/removeLabelIds/forward). Returns the
        created filter object."""
        body = {"criteria": criteria, "action": action}
        return callAPI(
            self.service.users()
            .settings()
            .filters()
            .create(userId=self.userID, body=body)
        )

    @_check_valid_interface
    def deleteFilter(self, filter_id):
        """Delete a filter by id."""
        callAPI(
            self.service.users()
            .settings()
            .filters()
            .delete(userId=self.userID, id=filter_id)
        )
        return {"deleted": filter_id}

    @_check_valid_interface
    def process(self, rules, archive_root, num_messages=1000, reporter=None, cancel=None):
        """Download the latest ``num_messages`` messages mailbox-wide, then
        apply the label -> action rules to them. Returns the summary dict."""
        from gmail_parser.processor import process_messages

        self.loadRecent(num_messages, reporter=reporter)
        label_map = self.getLabelMap()
        return process_messages(
            self.messages,
            rules,
            label_map,
            os.path.expanduser(archive_root),
            reporter=reporter,
            cancel=cancel,
        )

    @_check_valid_interface
    def Outbox(self, limit=50000):
        self._log("Constructing Outbox.")
        self.messages.clear()
        all_mail = self._get_all_mail(limit)
        for i in progressbar.progressbar(range(len(all_mail))):
            json_message = all_mail[i]
            full_json_message = callAPI(
                self.service.users()
                .messages()
                .get(userId=self.userID, id=json_message["id"])
            )
            if (
                "labelIds" in full_json_message
                and "SENT" in full_json_message["labelIds"]
            ):
                self.messages.append(GMailMessage(full_json_message, self))
        self._log("%d total OUTBOX messages." % len(self.messages))
        self._log("%d -> %d messages." % (len(all_mail), len(self.messages)))
        return self

    @_check_valid_interface
    def fromDates(self, startDate=None, endDate=None):
        new_messages = list()
        if not startDate is None and not endDate is None:
            date0 = datetime.strptime(startDate, "%m/%d/%Y")
            date1 = datetime.strptime(endDate, "%m/%d/%Y")
            new_messages = list()
            for message in self.messages:
                if message.getDate() >= date0 and message.getDate() <= date1:
                    new_messages.append(message)
        elif not startDate is None and endDate is None:
            date0 = datetime.strptime(startDate, "%m/%d/%Y")
            new_messages = list()
            for message in self.messages:
                if message.getDate() >= date0:
                    new_messages.append(message)
        elif startDate is None and not endDate is None:
            date1 = datetime.strptime(endDate, "%m/%d/%Y")
            new_messages = list()
            for message in self.messages:
                if message.getDate() <= date1:
                    new_messages.append(message)
        else:
            new_messages = self.messages
        self._log("%d -> %d messages." % (len(self.messages), len(new_messages)))
        return self._scoped_copy(new_messages)

    @_check_valid_interface
    def fromSenders(self, senders):
        new_messages = [
            message for message in self.messages if message.getSenderEmail() in senders
        ]
        self._log("%d -> %d messages." % (len(self.messages), len(new_messages)))
        return self._scoped_copy(new_messages)

    @_check_valid_interface
    def fromSubject(self, subject_strings):
        new_messages = [
            message for message in self.messages if message.hasSubject(subject_strings)
        ]
        self._log("%d -> %d messages." % (len(self.messages), len(new_messages)))
        return self._scoped_copy(new_messages)

    @_check_valid_interface
    def fromContents(self, content_strings):
        new_messages = [
            message for message in self.messages if message.hasText(content_strings)
        ]
        self._log("%d -> %d messages." % (len(self.messages), len(new_messages)))
        return self._scoped_copy(new_messages)

    @_check_valid_interface
    def fromUnread(self):
        new_messages = [message for message in self.messages if not message.isRead()]
        self._log("%d -> %d messages." % (len(self.messages), len(new_messages)))
        return self._scoped_copy(new_messages)

    @_check_valid_interface
    def getMessages(self):
        return self.messages

    @_check_valid_interface
    def markAllAsRead(self):
        num_messages = len(self.messages)
        for i in progressbar.progressbar(range(num_messages)):
            message = self.messages[i]
            message.markAsRead()

    @_check_valid_interface
    def markAllAsUnread(self):
        num_messages = len(self.messages)
        for i in progressbar.progressbar(range(num_messages)):
            message = self.messages[i]
            message.markAsUnread()

    @_check_valid_interface
    def moveAllToTrash(self):
        num_messages = len(self.messages)
        for i in progressbar.progressbar(range(num_messages)):
            message = self.messages[i]
            message.moveToTrash()

    @_check_valid_interface
    def removeAllFromTrash(self):
        num_messages = len(self.messages)
        for i in progressbar.progressbar(range(num_messages)):
            message = self.messages[i]
            message.removeFromTrash()

    @_check_valid_interface
    def clean(self):
        blacklist = ("CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL")
        num_trashed = 0
        num_messages = len(self.messages)
        for i in progressbar.progressbar(range(num_messages)):
            message = self.messages[i]
            for removal_category in blacklist:
                if removal_category in message.getLabels():
                    message.moveToTrash()
                    num_trashed += 1
                    break
        self._log("%d/%d messages moved to trash." % (num_trashed, num_messages))

    @_check_valid_interface
    def getSenders(self):
        senders = dict()
        for message in self.messages:
            sender = message.getSenderEmail()
            if sender in senders:
                senders[sender] += 1
            else:
                senders[sender] = 1
        return dict(sorted(senders.items(), key=lambda item: -item[1]))


class GBotCorpus(GMailCorpus):
    def __init__(self, email_address, messages=None, **kwargs):
        super(GBotCorpus, self).__init__(
            email_address,
            messages=messages,
            gmail_refresh_file=GPD.getKwargsOrDefault("gbot_refresh_file", **kwargs),
            headless=True,
            **kwargs
        )

    @GMailCorpus._check_valid_interface
    def Inbox(self, limit=50000):
        self._log("Constructing GBot Inbox.")
        self.messages.clear()
        all_mail = self._get_all_mail(limit)
        for i in progressbar.progressbar(range(len(all_mail))):
            json_message = all_mail[i]
            thread_json_message = callAPI(
                self.service.users()
                .threads()
                .get(userId=self.userID, id=json_message["threadId"])
            )
            thread_msgs_json = thread_json_message["messages"]
            if (
                "labelIds" in thread_msgs_json[0]
                and "INBOX" in thread_msgs_json[0]["labelIds"]
            ):
                for json_object in thread_msgs_json:
                    if (
                        "parts" in json_object["payload"]
                        and "filename" in json_object["payload"]["parts"][0]
                        and json_object["payload"]["parts"][0]["filename"]
                        == "text_0.txt"
                    ):
                        messageId = json_object["id"]
                        attachmentId = json_object["payload"]["parts"][0]["body"][
                            "attachmentId"
                        ]
                        dataMsg = callAPI(
                            self.service.users()
                            .messages()
                            .attachments()
                            .get(
                                userId=self.userID, messageId=messageId, id=attachmentId
                            )
                        )
                        json_object["text_attachment_data"] = dataMsg["data"]
                self.messages.append(GMailMessage(thread_msgs_json, self))
        self._log("%d total INBOX messages." % len(self.messages))
        self._log("%d -> %d messages." % (len(all_mail), len(self.messages)))
        return self

    @GMailCorpus._check_valid_interface
    def Outbox(self, limit=50000):
        self._log("Outbox not supported for GBot.")
        return self


class JournalCorpus(GMailCorpus):
    def __init__(self, email_address, messages=None, **kwargs):
        super(JournalCorpus, self).__init__(
            email_address,
            messages=messages,
            gmail_refresh_file=GPD.getKwargsOrDefault("journal_refresh_file", **kwargs),
            headless=True,
            **kwargs
        )

    @GMailCorpus._check_valid_interface
    def Inbox(self, limit=50000):
        self._log("Constructing Journal Inbox.")
        self.messages.clear()
        all_mail = self._get_all_mail(limit)
        for i in progressbar.progressbar(range(len(all_mail))):
            json_message = all_mail[i]
            thread_json_message = callAPI(
                self.service.users()
                .threads()
                .get(userId=self.userID, id=json_message["threadId"])
            )
            thread_msgs_json = thread_json_message["messages"]
            if (
                "labelIds" in thread_msgs_json[0]
                and "INBOX" in thread_msgs_json[0]["labelIds"]
            ):
                for json_object in thread_msgs_json:
                    if (
                        "parts" in json_object["payload"]
                        and "filename" in json_object["payload"]["parts"][0]
                        and json_object["payload"]["parts"][0]["filename"]
                        == "text_0.txt"
                    ):
                        messageId = json_object["id"]
                        attachmentId = json_object["payload"]["parts"][0]["body"][
                            "attachmentId"
                        ]
                        dataMsg = callAPI(
                            self.service.users()
                            .messages()
                            .attachments()
                            .get(
                                userId=self.userID, messageId=messageId, id=attachmentId
                            )
                        )
                        json_object["text_attachment_data"] = dataMsg["data"]
                self.messages.append(GMailMessage(thread_msgs_json, self))
        self._log("%d total INBOX messages." % len(self.messages))
        self._log("%d -> %d messages." % (len(all_mail), len(self.messages)))
        return self

    @GMailCorpus._check_valid_interface
    def Outbox(self, limit=50000):
        self._log("Outbox not supported for Journal.")
        return self
