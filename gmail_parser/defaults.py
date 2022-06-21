import os

class GmailParserDefaults:
    # minimum setup needed is to have this file exist (https://pythonhosted.org/PyDrive/quickstart.html):
    DRIVE_SECRETS_FILE = os.path.expanduser("~/google_secrets/pydrive_secrets/client_secrets.json")
    # Go to your Google Developers Console account and create a project called "GmailParser".
    # Under the project, enable the GMail API. You'll want all available scopes.
    # Under project credentials, create new "OAuth 2.0 Client" credentials to allow for accessing personal user data. 
    #     It'll have you design a consent page and will give you the needed client_secret.json file, which you can rename.
    GMAIL_SECRETS_PATH = os.path.expanduser("~/google_secrets/gmail_parser_secrets")
    GMAIL_SECRETS_HASH = "1C7NDyyEbgUQTAAX98K8FQmUn2plA9VP-"
    GMAIL_SECRETS_JSON = os.path.join(GMAIL_SECRETS_PATH, "gmailparser_client_secret.json")
    GMAIL_REFRESH_FILE = os.path.join(GMAIL_SECRETS_PATH, "gmailparser_refresh.txt")
    GMAIL_CORPUS_SCOPE = [
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
    ENABLE_LOGGING = True

    @staticmethod
    def getKwargsOrDefault(argname, **kwargs):
        # Possible util function args
        argname_mapping = {
            "drive_secrets_file": GmailParserDefaults.DRIVE_SECRETS_FILE,
            "gmail_secrets_path": GmailParserDefaults.GMAIL_SECRETS_PATH,
            "gmail_secrets_hash": GmailParserDefaults.GMAIL_SECRETS_HASH,
            "gmail_secrets_json": GmailParserDefaults.GMAIL_SECRETS_JSON,
            "gmail_refresh_file": GmailParserDefaults.GMAIL_REFRESH_FILE,
            "gmail_corpus_scope": GmailParserDefaults.GMAIL_CORPUS_SCOPE,
            "enable_logging": GmailParserDefaults.ENABLE_LOGGING,
        }
        return kwargs[argname] if argname in kwargs else argname_mapping[argname]
