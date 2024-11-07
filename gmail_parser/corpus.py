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
    def _get_all_mail(self, limit):
        json_messages = list()
        list_response = callAPI(
            self.service.users()
            .messages()
            .list(userId=self.userID, maxResults=limit, labelIds=["INBOX"])
        )
        self._log("Front Page -> %d messages." % len(list_response["messages"]))
        json_messages.extend(list_response["messages"])
        while "nextPageToken" in list_response and len(json_messages) < limit:
            page_token = list_response["nextPageToken"]
            list_response = callAPI(
                self.service.users()
                .messages()
                .list(
                    userId=self.userID,
                    maxResults=limit - len(json_messages),
                    pageToken=page_token,
                    labelIds=["INBOX"],
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
    def Inbox(self, limit=50000):
        self._log("Constructing Inbox.")
        self.messages.clear()
        all_mail = self._get_all_mail(limit)
        for i in progressbar.progressbar(range(len(all_mail))):
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
        self._log("%d total INBOX messages." % len(self.messages))
        self._log("%d -> %d messages." % (len(all_mail), len(self.messages)))
        return self

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
