import os


class GmailParserDefaults:
    GMAIL_SECRETS_JSON = "~/secrets/google/client_secrets.json"
    GMAIL_REFRESH_FILE = "~/secrets/google/refresh.json"
    GBOT_REFRESH_FILE = "~/secrets/google/bot_refresh.json"
    JOURNAL_REFRESH_FILE = "~/secrets/google/journal_refresh.json"
    ENABLE_LOGGING = False

    @staticmethod
    def getKwargsOrDefault(argname, **kwargs):
        # Possible util function args
        argname_mapping = {
            "gmail_secrets_json": GmailParserDefaults.GMAIL_SECRETS_JSON,
            "gmail_refresh_file": GmailParserDefaults.GMAIL_REFRESH_FILE,
            "gbot_refresh_file": GmailParserDefaults.GBOT_REFRESH_FILE,
            "journal_refresh_file": GmailParserDefaults.JOURNAL_REFRESH_FILE,
            "enable_logging": GmailParserDefaults.ENABLE_LOGGING,
        }
        return kwargs[argname] if argname in kwargs else argname_mapping[argname]
