from datetime import datetime
import base64
import re
import html2text

HTMLHANDLER = html2text.HTML2Text()
HTMLHANDLER.ignore_links = False

def callAPI(api_call):
    response = dict()
    try:
        response = api_call.execute()
    except Exception as e:
        print(e)
    return response

class GMailMessage(object):
    def __init__(self, json_objects, corpus):
        json_object = json_objects[0]
        self.corpus = corpus
        self.date = ''
        self.subject = ''
        self.sender_name = ''
        self.sender_email = ''
        self.is_trash = False
        self.content = ''
        self.id = json_object['id']
        for payload_header in json_object['payload']['headers']:
            if payload_header['name'] == 'Subject':
                self.subject = payload_header['value']
            elif payload_header['name'] == 'From':
                from_str = payload_header['value']
                if '<' in from_str:
                    from_data = re.split('<|>', from_str)
                    self.sender_name = from_data[0]
                    self.sender_email = from_data[1]
                else:
                    self.sender_name = from_str
                    self.sender_email = from_str
        self.labels = list()
        if 'labelIds' in json_object:
            self.labels = json_object['labelIds']
        for json_object in json_objects:
            if 'body' in json_object['payload'] and 'data' in json_object['payload']['body']:
                self.content += self._gmail_decode_string(json_object['payload']['body']['data'])
            elif 'parts' in json_object['payload']:
                for part in json_object['payload']['parts']:
                    if part['mimeType'] == 'text/plain' and 'body' in part and 'data' in part['body']:
                        self.content += self._gmail_decode_string(part['body']['data'])
                    elif part['mimeType'] == 'multipart/alternative' and 'parts' in part:
                        for partpart in part['parts']:
                            if partpart['mimeType'] == 'text/plain' and 'body' in partpart and 'data' in partpart['body']:
                                self.content += self._gmail_decode_string(partpart['body']['data'])
        self.content = self.content.replace('\r','')
        self.is_html = '<html' in self.content
        internal_secs = float(json_object['internalDate']) / 1000.0
        self.date = datetime.fromtimestamp(internal_secs)
        self.json = json_objects

    def _gmail_decode_string(self, string): 
        return base64.b64decode(string.replace('-','+').replace('_','/')).decode("utf-8")

    def getLabels(self):
        return self.labels

    def getContent(self):
        return self.content

    def getText(self):
        if self.is_html:
            return HTMLHANDLER.handle(self.content)
        else:
            return self.content

    def getDate(self):
        return self.date

    def getSubject(self):
        return self.subject

    def getSenderName(self):
        return self.sender_name

    def getSenderEmail(self):
        return self.sender_email

    def hasSubject(self, subject_strings):
        for subject_string in subject_strings:
            if subject_string.lower() in self.subject.lower():
                return True
        return False

    def hasText(self, content_strings):
        raw_text = self.getText().lower()
        for content_string in content_strings:
            if content_string.lower() in raw_text:
                return True
        return False

    def markAsRead(self):
        if not self.isRead():
            resource = {'addLabelIds': [], 'removeLabelIds': ['UNREAD']}
            callAPI(self.corpus.service.users().messages().modify(userId=self.corpus.userID,id=self.id,body=resource))
            self.corpus._log('Message id=%s marked as read.' % self.id)
            self.labels.remove('UNREAD')

    def markAsUnread(self):
        if self.isRead():
            resource = {'addLabelIds': ['UNREAD'], 'removeLabelIds': []}
            callAPI(self.corpus.service.users().messages().modify(userId=self.corpus.userID,id=self.id,body=resource))
            self.corpus._log('Message id=%s marked as unread.' % self.id)
            self.labels.append('UNREAD')

    def isRead(self):
        return not ('UNREAD' in self.labels)

    def moveToTrash(self):
        if not self.isTrash():
            callAPI(self.corpus.service.users().messages().trash(userId=self.corpus.userID,id=self.id))
            self.corpus._log('Message id=%s moved to trash.' % self.id)
            self.is_trash = True

    def removeFromTrash(self):
        if self.isTrash():
            callAPI(self.corpus.service.users().messages().untrash(userId=self.corpus.userID,id=self.id))
            self.corpus._log('Message id=%s removed from trash.' % self.id)
            self.is_trash = False

    def isTrash(self):
        return self.is_trash

    def stringify(self):
        return "[{}] {} -> <\"{}\", {}>".format(self.date, self.sender_email, self.subject, self.labels)

    def __repr__(self):
        return self.stringify()

    def __str__(self):
        return self.stringify()
