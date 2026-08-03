import os
import sys
import json
import base64
from flask import Flask, request
from email.mime.text import MIMEText
from dotenv import load_dotenv
from googleapiclient.discovery import build

sys.path.append('src')
from email_reader import authenticate_gmail

load_dotenv()

app = Flask(__name__)

CONTEXT_FILE = 'email_context.json'


def load_context():
    if os.path.exists(CONTEXT_FILE):
        with open(CONTEXT_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_context(context):
    with open(CONTEXT_FILE, 'w') as f:
        json.dump(context, f, indent=2)


def update_email_context(email_id, sender, subject):
    context = load_context()
    context[email_id] = {'sender': sender, 'subject': subject}
    save_context(context)
    print(f"Context saved for email from {sender}")


def send_gmail_reply(to_email, subject, body):
    """
    Sends an email reply via Gmail API.
    """
    creds   = authenticate_gmail()
    service = build('gmail', 'v1', credentials=creds)

    reply_subject = subject if subject.startswith('Re:') else f"Re: {subject}"

    message = MIMEText(body)
    message['to']      = to_email
    message['subject'] = reply_subject

    raw  = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
    sent = service.users().messages().send(
        userId='me',
        body={'raw': raw}
    ).execute()

    print(f"Reply sent to {to_email} - Message ID: {sent['id']}")
    return sent['id']


@app.route('/whatsapp-reply', methods=['POST'])
def whatsapp_reply():
    """
    Twilio webhook - fires when you send a WhatsApp message to the sandbox.
    Format: REPLY 1 Your message here
    """
    incoming_msg = request.form.get('Body', '').strip()
    print(f"\nIncoming WhatsApp message: {incoming_msg}")

    if not incoming_msg.upper().startswith('REPLY'):
        print("Not a reply command - ignoring.")
        return "OK", 200

    parts = incoming_msg.split(' ', 2)
    if len(parts) < 3:
        return "OK", 200

    try:
        email_num  = int(parts[1])
        reply_body = parts[2]
    except ValueError:
        return "OK", 200

    last_email_context = load_context()
    email_keys         = list(last_email_context.keys())

    if not email_keys:
        print("No email context found - run the agent first.")
        return "OK", 200

    index = email_num - 1
    if index < 0 or index >= len(email_keys):
        print(f"Email number {email_num} not found.")
        return "OK", 200

    email_id = email_keys[index]
    context  = last_email_context[email_id]

    print(f"Sending reply to {context['sender']}...")

    try:
        send_gmail_reply(
            to_email=context['sender'],
            subject=context['subject'],
            body=reply_body
        )
        print(f"Reply sent successfully to {context['sender']}")

        from whatsapp_sender import send_whatsapp
        send_whatsapp(
            f"Reply sent to: {context['sender']}\n"
            f"Subject: Re: {context['subject']}\n"
            f"Message: {reply_body}"
        )

    except Exception as e:
        print(f"Failed to send reply: {e}")

    return "OK", 200


if __name__ == '__main__':
    print("Reply webhook server starting on port 5000...")
    print("Waiting for WhatsApp replies...")
    print("\nHow to reply: REPLY 1 Your message here\n")
    app.run(port=5000, debug=False)