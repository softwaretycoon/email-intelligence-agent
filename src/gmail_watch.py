import os
import sys
import json
from dotenv import load_dotenv

sys.path.append('src')
from email_reader import get_gmail_service

load_dotenv()

# ── Your Pub/Sub topic full name ──────────────────────────────────────────────
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
TOPIC_NAME = f"projects/{PROJECT_ID}/topics/gmail-notifications"


def start_gmail_watch():
    """
    Tells Gmail to send push notifications to your Pub/Sub topic
    every time a new email arrives in the inbox.
    Gmail watch expires after 7 days so we renew it automatically.
    """
    service = get_gmail_service()

    request_body = {
        'labelIds': ['INBOX'],
        'topicName': TOPIC_NAME
    }

    response = service.users().watch(
        userId='me',
        body=request_body
    ).execute()

    print(f"Gmail watch started successfully.")
    print(f"History ID: {response.get('historyId')}")
    print(f"Expiration: {response.get('expiration')}")
    return response


def stop_gmail_watch():
    """
    Stops Gmail push notifications.
    """
    service = get_gmail_service()
    service.users().stop(userId='me').execute()
    print("Gmail watch stopped.")


if __name__ == '__main__':
    print("Starting Gmail watch...")
    result = start_gmail_watch()
    print(f"Done — {result}")