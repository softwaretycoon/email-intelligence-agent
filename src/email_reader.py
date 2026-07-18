import os
import json
import base64
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# ── What permissions we need from Gmail ──────────────────────────────────────
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send'
]

# ── Path to local credential files ───────────────────────────────────────────
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE       = 'token.json'


def authenticate_gmail():
    """
    Logs into Gmail using OAuth.
    - On Railway: reads credentials from environment variables
    - Locally: reads from credentials.json and token.json files
    """
    creds = None

    # ── Try Railway environment variables first ───────────────────
    google_token = os.getenv("GOOGLE_TOKEN")
    if google_token:
        try:
            token_data = json.loads(google_token)
            creds = Credentials.from_authorized_user_info(token_data, SCOPES)
            print("Using Google token from environment variable.")
        except Exception as e:
            print(f"Failed to load token from env: {e}")

    # ── Fall back to local token.json ─────────────────────────────
    elif os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        print("Using Google token from local file.")

    # ── Refresh token if expired ──────────────────────────────────
    if creds and creds.expired and creds.refresh_token:
        print("Token expired — refreshing...")
        creds.refresh(Request())

        # Save refreshed token
        if os.getenv("GOOGLE_TOKEN"):
            # On Railway — print the new token so you can update the variable
            print("\n⚠️  TOKEN REFRESHED — Update GOOGLE_TOKEN in Railway with:")
            print(creds.to_json())
            print()
        else:
            # Locally — save to token.json
            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())

    # ── If no valid creds, run local browser login ────────────────
    if not creds or not creds.valid:
        if os.getenv("GOOGLE_TOKEN"):
            raise Exception(
                "GOOGLE_TOKEN is invalid or expired. "
                "Please generate a new token locally and update Railway."
            )
        else:
            # Local only — open browser for login
            google_credentials = os.getenv("GOOGLE_CREDENTIALS")
            if google_credentials:
                cred_data = json.loads(google_credentials)
                flow = InstalledAppFlow.from_client_config(cred_data, SCOPES)
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    CREDENTIALS_FILE, SCOPES
                )
            creds = flow.run_local_server(port=0)
            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())

    return creds


def get_gmail_service():
    """
    Returns an authenticated Gmail service object.
    """
    creds = authenticate_gmail()
    return build('gmail', 'v1', credentials=creds)


def get_unread_emails(max_results=5, service=None):
    """
    Fetches unread emails from Gmail inbox.
    Returns a list of emails with sender, subject and body.
    """
    if service is None:
        service = get_gmail_service()

    # Search for unread emails in inbox
    results = service.users().messages().list(
        userId='me',
        labelIds=['INBOX', 'UNREAD'],
        maxResults=max_results
    ).execute()

    messages = results.get('messages', [])

    if not messages:
        print("No unread emails found.")
        return []

    emails = []

    for msg in messages:
        msg_data = service.users().messages().get(
            userId='me',
            id=msg['id'],
            format='full'
        ).execute()

        headers = msg_data['payload']['headers']
        sender  = next((h['value'] for h in headers if h['name'] == 'From'),    'Unknown')
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        date    = next((h['value'] for h in headers if h['name'] == 'Date'),    'Unknown')

        body = extract_body(msg_data['payload'])

        emails.append({
            'id':      msg['id'],
            'sender':  sender,
            'subject': subject,
            'date':    date,
            'body':    body[:3000]
        })

    print(f"Found {len(emails)} unread email(s).")
    return emails


def extract_body(payload):
    """
    Extracts plain text body from an email payload.
    Handles both simple and multipart emails.
    """
    body = ''

    if 'parts' in payload:
        for part in payload['parts']:
            if part['mimeType'] == 'text/plain':
                data = part['body'].get('data', '')
                if data:
                    body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                    break
            elif part['mimeType'] == 'multipart/alternative':
                body = extract_body(part)
                if body:
                    break
    else:
        data = payload['body'].get('data', '')
        if data:
            body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')

    return body.strip()


def mark_as_read(service, email_id):
    """
    Marks a single email as read in Gmail.
    """
    service.users().messages().modify(
        userId='me',
        id=email_id,
        body={'removeLabelIds': ['UNREAD']}
    ).execute()
    print(f"Email {email_id} marked as read.")


# ── Test this file directly ───────────────────────────────────────────────────
if __name__ == '__main__':
    print("Connecting to Gmail...")
    emails = get_unread_emails(max_results=3)

    for i, email in enumerate(emails, 1):
        print(f"\n{'='*50}")
        print(f"Email {i}")
        print(f"From:    {email['sender']}")
        print(f"Subject: {email['subject']}")
        print(f"Date:    {email['date']}")
        print(f"Body preview: {email['body'][:200]}...")