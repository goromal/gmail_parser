import os

class GmailParserDefaults:
    GMAIL_SECRETS_JSON = os.path.expanduser("~/secrets/gmail/secrets.json")
    GMAIL_REFRESH_FILE = os.path.expanduser("~/secrets/gmail/refresh.json")
    GBOT_REFRESH_FILE = os.path.expanduser("~/secrets/gmail/bot_refresh.json")
    JOURNAL_REFRESH_FILE = os.path.expanduser("~/secrets/gmail/journal_refresh.json")
    GMAIL_CORPUS_SCOPE = [
        'openid',
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/userinfo.profile',
        'https://www.googleapis.com/auth/gmail.labels',
        'https://www.googleapis.com/auth/gmail.send',
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.compose',
        'https://www.googleapis.com/auth/gmail.insert',
        'https://www.googleapis.com/auth/gmail.modify',
        'https://www.googleapis.com/auth/gmail.settings.basic',
        'https://www.googleapis.com/auth/gmail.settings.sharing',
        'https://mail.google.com/'
    ]
    ENABLE_LOGGING = False

    @staticmethod
    def getKwargsOrDefault(argname, **kwargs):
        # Possible util function args
        argname_mapping = {
            "gmail_secrets_json": GmailParserDefaults.GMAIL_SECRETS_JSON,
            "gmail_refresh_file": GmailParserDefaults.GMAIL_REFRESH_FILE,
            "gbot_refresh_file": GmailParserDefaults.GBOT_REFRESH_FILE,
            "journal_refresh_file": GmailParserDefaults.JOURNAL_REFRESH_FILE,
            "gmail_corpus_scope": GmailParserDefaults.GMAIL_CORPUS_SCOPE,
            "enable_logging": GmailParserDefaults.ENABLE_LOGGING,
        }
        return kwargs[argname] if argname in kwargs else argname_mapping[argname]
