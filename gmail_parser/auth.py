import os
import json
import httplib2
from gmail_parser.defaults import GmailParserDefaults as GPD
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import oauth2client
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow

def getSecretsFromDrive(**kwargs):
    drive_secrets_file = GPD.getKwargsOrDefault("drive_secrets_file", **kwargs)
    gmail_secrets_path = GPD.getKwargsOrDefault("gmail_secrets_path", **kwargs)
    gmail_secrets_hash = GPD.getKwargsOrDefault("gmail_secrets_hash", **kwargs)

    GoogleAuth.DEFAULT_SETTINGS["client_config_file"] = drive_secrets_file
    gauth = GoogleAuth()
    gauth.LocalWebserverAuth()
    drive = GoogleDrive(gauth)
    os.makedirs(gmail_secrets_path)

    file_list = drive.ListFile({"q": f"'{gmail_secrets_hash}' in parents"}).GetList()
    for f in file_list:
        print(f"Downloading {f['title']} to {gmail_secrets_path}...")
        fname = os.path.join(gmail_secrets_path, f['title'])
        f_ = drive.CreateFile({'id': f['id']})
        f_.GetContentFile(fname)

def getGmailCredentials(**kwargs):
    gmail_secrets_json = GPD.getKwargsOrDefault("gmail_secrets_json", **kwargs)
    gmail_refresh_file = GPD.getKwargsOrDefault("gmail_refresh_file", **kwargs)

    with open(gmail_refresh_file, "r") as refreshfile, open(gmail_secrets_json, "r") as secretsfile:
        refresh_token = refreshfile.read()
        secrets_json = json.load(secretsfile)
        credentials = oauth2client.client.GoogleCredentials(
            access_token = None,
            client_id = secrets_json["installed"]["client_id"],
            client_secret = secrets_json["installed"]["client_secret"],
            refresh_token = refresh_token,
            token_expiry = None,
            token_uri = "https://accounts.google.com/o/oauth2/token",
            user_agent = "google_tools"
        )
        credentials.refresh(credentials.authorize(httplib2.Http()))
        return credentials

def getGmailService(**kwargs):
    gmail_secrets_json = GPD.getKwargsOrDefault("gmail_secrets_json", **kwargs)
    gmail_refresh_file = GPD.getKwargsOrDefault("gmail_refresh_file", **kwargs)

    try:
        credentials=getGmailCredentials(gmail_secrets_json=gmail_secrets_json, gmail_refresh_file=gmail_refresh_file)
    except oauth2client.client.HttpAccessTokenRefreshError:
        print("Something wrong with credentials/refresh file. Attempting to obtain a new refresh file.")
        full_scope_list = ['openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile']
        full_scope_list += GPD.GMAIL_CORPUS_SCOPE
        flow = Flow.from_client_secrets_file(
            gmail_secrets_json,
            scopes=full_scope_list,
            redirect_uri='urn:ietf:wg:oauth:2.0:oob'
        )
        auth_uri = flow.authorization_url()
        print(f"Please visit {auth_uri[0]}")
        code = input("Enter the authorization code: ")
        flow.fetch_token(code=code)
        with open(gmail_refresh_file, "w") as refreshfile:
            refreshfile.write(flow.credentials.refresh_token)
        credentials=getGmailCredentials(gmail_secrets_json=gmail_secrets_json, gmail_refresh_file=gmail_refresh_file)
    
    return build("gmail", "v1", credentials=credentials)