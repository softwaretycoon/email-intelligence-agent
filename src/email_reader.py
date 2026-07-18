import os
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

# ── Path to your credentials file ────────────────────────────────────────────
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE       = 'token.json'


def authenticate_gmail():
    """
    Logs into Gmail using OAuth.
    First run: opens browser for you to approve access.
    After that: uses saved token.json automatically.
    """
    creds = None

    # If we already logged in before, load the saved token
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # If no valid token, ask user to log in via browser
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the token so we don't need to log in every time
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    return creds


def get_unread_emails(max_results=5, service=None):
    """
    Fetches unread emails from Gmail inbox.
    Returns a list of emails with sender, subject and body.
    """
    if service is None:
        creds   = authenticate_gmail()
        service = build('gmail', 'v1', credentials=creds)

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
        # Get the full email details
        msg_data = service.users().messages().get(
            userId='me',
            id=msg['id'],
            format='full'
        ).execute()

        # Pull out the headers (sender, subject, date)
        headers = msg_data['payload']['headers']
        sender  = next((h['value'] for h in headers if h['name'] == 'From'),  'Unknown')
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        date    = next((h['value'] for h in headers if h['name'] == 'Date'),   'Unknown')

        # Pull out the email body
        body = extract_body(msg_data['payload'])

        emails.append({
            'id':      msg['id'],
            'sender':  sender,
            'subject': subject,
            'date':    date,
            'body':    body[:3000]  # limit to 3000 chars for GPT
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
        # Multipart email — look through each part
        for part in payload['parts']:
            if part['mimeType'] == 'text/plain':
                data = part['body'].get('data', '')
                if data:
                    body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                    break
            elif part['mimeType'] == 'multipart/alternative':
                # Nested multipart
                body = extract_body(part)
                if body:
                    break
    else:
        # Simple single-part email
        data = payload['body'].get('data', '')
        if data:
            body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')

    return body.strip()
def mark_as_read(service, email_id):
    """
    Marks a single email as read in Gmail
    by removing the UNREAD label.
    """
    service.users().messages().modify(
        userId='me',
        id=email_id,
        body={'removeLabelIds': ['UNREAD']}
    ).execute()
    print(f"Email {email_id} marked as read.")


def get_gmail_service():
    """
    Returns an authenticated Gmail service object
    so other files can use it.
    """
    creds = authenticate_gmail()
    return build('gmail', 'v1', credentials=creds)

# ── Test this file directly ───────────────────────────────────────────────────
if __name__ == '__main__':
    print("Connecting to Gmail...")
    emails = get_unread_emails(max_results=5)

    for i, email in enumerate(emails, 1):
        print(f"\n{'='*50}")
        print(f"Email {i}")
        print(f"From:    {email['sender']}")
        print(f"Subject: {email['subject']}")
        print(f"Date:    {email['date']}")
        print(f"Body preview: {email['body'][:200]}...")