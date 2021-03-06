import os
import sys
import logging
import time
from datetime import datetime
import progressbar

from gmail_parser.auth import getSecretsFromDrive, getGmailService
from gmail_parser.utils import callAPI, GMailMessage
from gmail_parser.defaults import GmailParserDefaults as GPD

class GMailCorpus(object):
    def __init__(self, email_address, messages=None, **kwargs):
        self.drive_secrets_file = GPD.getKwargsOrDefault("drive_secrets_file", **kwargs)
        self.gmail_secrets_path = GPD.getKwargsOrDefault("gmail_secrets_path", **kwargs)
        self.gmail_secrets_hash = GPD.getKwargsOrDefault("gmail_secrets_hash", **kwargs)
        self.gmail_secrets_json = GPD.getKwargsOrDefault("gmail_secrets_json", **kwargs)
        self.gmail_refresh_file = GPD.getKwargsOrDefault("gmail_refresh_file", **kwargs)
        self.enable_logging = GPD.getKwargsOrDefault("enable_logging", **kwargs)

        if self.enable_logging:
            logging.basicConfig(filename='LOG-google_tools_GMAIL_%s.log' % time.strftime('%Y%m%d-%H%M%S'), level=logging.INFO)
            logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))

        if not os.path.exists(self.gmail_secrets_json) or not os.path.exists(self.gmail_refresh_file):
            getSecretsFromDrive(
                drive_secrets_file = self.drive_secrets_file,
                gmail_secrets_path = self.gmail_secrets_path,
                gmail_secrets_hash = self.gmail_secrets_hash
            )

        self.service = getGmailService(
            gmail_secrets_json = self.gmail_secrets_json,
            gmail_refresh_file = self.gmail_refresh_file
        )
        
        self.userID = email_address
        
        if messages is None:
            self.messages = list()
        else:
            self.messages = messages

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.service.close()

    def _scoped_copy(self, messages):
        return GMailCorpus(self.userID,
                           messages,
                           drive_secrets_file=self.drive_secrets_file,
                           gmail_secrets_path=self.gmail_secrets_path,
                           gmail_secrets_hash=self.gmail_secrets_hash,
                           gmail_secrets_json=self.gmail_secrets_json,
                           gmail_refresh_file=self.gmail_refresh_file,
                           enable_logging=self.enable_logging
                          )

    def _log(self, msg):
        if self.enable_logging:
            logging.info('[GMAILCORPUS] ' + msg)

    def _logwarn(self, msg):
        if self.enable_logging:
            logging.warn('[GMAILCORPUS] ' + msg)

    def _get_all_mail(self, limit):
        json_messages = list()
        list_response = callAPI(self.service.users().messages().list(userId=self.userID, maxResults=limit))
        self._log('Front Page -> %d messages.' % len(list_response['messages']))
        json_messages.extend(list_response['messages'])
        while 'nextPageToken' in list_response and len(json_messages) < limit:
            page_token = list_response['nextPageToken']
            list_response = callAPI(self.service.users().messages().list(userId=self.userID,maxResults=limit-len(json_messages),pageToken=page_token))
            if 'messages' in list_response:
                self._log('Page %s -> %d messages.' % (page_token, len(list_response['messages'])))
                json_messages.extend(list_response['messages'])
        self._log('%d total messages.' % len(json_messages))
        return json_messages

    def Inbox(self, limit=50000):
        self._log('Constructing Inbox.')
        self.messages.clear()
        all_mail = self._get_all_mail(limit)
        for i in progressbar.progressbar(range(len(all_mail))):
            json_message = all_mail[i]
            thread_json_message = callAPI(self.service.users().threads().get(userId=self.userID,id=json_message['threadId']))
            thread_msgs_json = thread_json_message['messages']
            if 'labelIds' in thread_msgs_json[0] and 'INBOX' in thread_msgs_json[0]['labelIds']:
              self.messages.append(GMailMessage(thread_msgs_json, self))
        self._log('%d total INBOX messages.' % len(self.messages))
        self._log('%d -> %d messages.' % (len(all_mail), len(self.messages)))
        return self

    def Outbox(self, limit=50000):
        self._log('Constructing Outbox.')
        self.messages.clear()
        all_mail = self._get_all_mail(limit)
        for i in progressbar.progressbar(range(len(all_mail))):
            json_message = all_mail[i]
            full_json_message = callAPI(self.service.users().messages().get(userId=self.userID,id=json_message['id']))
            if 'labelIds' in full_json_message and 'SENT' in full_json_message['labelIds']:
                self.messages.append(GMailMessage(full_json_message, self))
        self._log('%d total OUTBOX messages.' % len(self.messages))
        self._log('%d -> %d messages.' % (len(all_mail), len(self.messages)))
        return self

    def fromDates(self, startDate=None, endDate=None):
        new_messages = list()
        if not startDate is None and not endDate is None:
            date0 = datetime.strptime(startDate, '%m/%d/%Y')
            date1 = datetime.strptime(endDate, '%m/%d/%Y')
            new_messages = list()
            for message in self.messages:
                if message.getDate() >= date0 and message.getDate() <= date1:
                    new_messages.append(message)
        elif not startDate is None and endDate is None:
            date0 = datetime.strptime(startDate, '%m/%d/%Y')
            new_messages = list()
            for message in self.messages:
                if message.getDate() >= date0:
                    new_messages.append(message)
        elif startDate is None and not endDate is None:
            date1 = datetime.strptime(endDate, '%m/%d/%Y')
            new_messages = list()
            for message in self.messages:
                if message.getDate() <= date1:
                    new_messages.append(message)
        else:
            new_messages = self.messages
        self._log('%d -> %d messages.' % (len(self.messages), len(new_messages)))
        return self._scoped_copy(new_messages)

    def fromSenders(self, senders):
        new_messages = [message for message in self.messages if message.getSenderEmail() in senders]
        self._log('%d -> %d messages.' % (len(self.messages), len(new_messages)))
        return self._scoped_copy(new_messages)

    def fromSubject(self, subject_strings):
        new_messages = [message for message in self.messages if message.hasSubject(subject_strings)]
        self._log('%d -> %d messages.' % (len(self.messages), len(new_messages)))
        return self._scoped_copy(new_messages)

    def fromContents(self, content_strings):
        new_messages = [message for message in self.messages if message.hasText(content_strings)]
        self._log('%d -> %d messages.' % (len(self.messages), len(new_messages)))
        return self._scoped_copy(new_messages)

    def fromUnread(self):
        new_messages = [message for message in self.messages if not message.isRead()]
        self._log('%d -> %d messages.' % (len(self.messages), len(new_messages)))
        return self._scoped_copy(new_messages)

    def getMessages(self):
        return self.messages

    def markAllAsRead(self):
        num_messages = len(self.messages)
        for i in progressbar.progressbar(range(num_messages)):
            message = self.messages[i]
            message.markAsRead()

    def markAllAsUnread(self):
        num_messages = len(self.messages)
        for i in progressbar.progressbar(range(num_messages)):
            message = self.messages[i]
            message.markAsUnread()

    def moveAllToTrash(self):
        num_messages = len(self.messages)
        for i in progressbar.progressbar(range(num_messages)):
            message = self.messages[i]
            message.moveToTrash()

    def removeAllFromTrash(self):
        num_messages = len(self.messages)
        for i in progressbar.progressbar(range(num_messages)):
            message = self.messages[i]
            message.removeFromTrash()

    def clean(self):
        blacklist = ('CATEGORY_PROMOTIONS', 'CATEGORY_SOCIAL')
        num_trashed = 0
        num_messages = len(self.messages)
        for i in progressbar.progressbar(range(num_messages)):
            message = self.messages[i]
            for removal_category in blacklist:
                if removal_category in message.getLabels():
                    message.moveToTrash()
                    num_trashed += 1
                    break
        self._log('%d/%d messages moved to trash.' % (num_trashed, num_messages))

    def getSenders(self):
        senders = dict()
        for message in self.messages:
            sender = message.getSenderEmail()
            if sender in senders:
                senders[sender] += 1
            else:
                senders[sender] = 1
        return dict(sorted(senders.items(), key=lambda item: -item[1]))