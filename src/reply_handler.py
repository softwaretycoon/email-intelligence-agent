import os
import sys
import json
import base64
from flask import Flask, request
from email.mime.text import MIMEText
from dotenv import load_dotenv
from googleapiclient.discovery import build

# ── Add src to path ───────────────────────────────────────────────────────────
sys.path.append('src')
from email_reader import authenticate_gmail

load_dotenv()

app = Flask(__name__)

# ── Context file path — shared between main.py and reply_handler.py ──────────
CONTEXT_FILE = 'email_context.json'


def load_context():
    """
    Loads email context from the JSON file.
    Returns empty dict if file does not exist.
    """
    if os.path.exists(CONTEXT_FILE):
        with open(CONTEXT_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_context(context):
    """
    Saves email context to the JSON file.
    """
    with open(CONTEXT_FILE, 'w') as f:
        json.dump(context, f, indent=2)


def update_email_context(email_id, sender, subject):
    """
    Saves the most recent email details so we can reply to it.
    Called from main.py after each email is summarised.
    Writes to email_context.json so reply_handler can read it.
    """
    context = load_context()
    context[email_id] = {
        'sender':  sender,
        'subject': subject
    }
    save_context(context)
    print(f"Context saved for email from {sender}")


def send_gmail_reply(to_email, subject, body):
    """
    Sends an email reply via Gmail API.
    """
    creds   = authenticate_gmail()
    service = build('gmail', 'v1', credentials=creds)

    # Build the reply email
    reply_subject = subject if subject.startswith('Re:') else f"Re: {subject}"

    message = MIMEText(body)
    message['to']      = to_email
    message['subject'] = reply_subject

    # Encode the message
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')

    # Send via Gmail API
    sent = service.users().messages().send(
        userId='me',
        body={'raw': raw}
    ).execute()

    print(f"Reply sent to {to_email} — Message ID: {sent['id']}")
    return sent['id']


@app.route('/whatsapp-reply', methods=['POST'])
def whatsapp_reply():
    """
    Twilio webhook endpoint.
    Fires every time you send a WhatsApp message back to the sandbox.
    Format your reply as:  REPLY <email_number> <your message>
    Example:               REPLY 1 Thanks for reaching out, I will get back to you tomorrow.
    """
    incoming_msg = request.form.get('Body', '').strip()
    print(f"\nIncoming WhatsApp message: {incoming_msg}")

    # ── Parse the reply command ───────────────────────────────────
    if not incoming_msg.upper().startswith('REPLY'):
        print("Not a reply command — ignoring.")
        return "OK", 200

    parts = incoming_msg.split(' ', 2)

    if len(parts) < 3:
        print("Invalid format. Use: REPLY <number> <message>")
        return "OK", 200

    try:
        email_num  = int(parts[1])  # which email number to reply to
        reply_body = parts[2]       # the actual reply message
    except ValueError:
        print("Invalid email number.")
        return "OK", 200

    # ── Load email context from JSON file ─────────────────────────
    last_email_context = load_context()
    email_keys         = list(last_email_context.keys())

    if not email_keys:
        print("No email context found — run the agent first.")
        return "OK", 200

    # Email numbers start at 1 so subtract 1 for index
    index = email_num - 1

    if index < 0 or index >= len(email_keys):
        print(f"Email number {email_num} not found. Only {len(email_keys)} email(s) in context.")
        return "OK", 200

    email_id = email_keys[index]
    context  = last_email_context[email_id]

    # ── Send the reply via Gmail ──────────────────────────────────
    print(f"Sending reply to {context['sender']}...")

    try:
        send_gmail_reply(
            to_email=context['sender'],
            subject=context['subject'],
            body=reply_body
        )
        print(f"✅ Reply sent successfully to {context['sender']}")

        # Send confirmation back to WhatsApp
        from whatsapp_sender import send_whatsapp
        send_whatsapp(
            f"✅ *Reply sent!*\n\n"
            f"To: {context['sender']}\n"
            f"Subject: Re: {context['subject']}\n\n"
            f"Message: {reply_body}"
        )

    except Exception as e:
        print(f"❌ Failed to send reply: {e}")

    return "OK", 200


# ── Run the webhook server ────────────────────────────────────────────────────
if __name__ == '__main__':
    print("🌐 Reply webhook server starting on port 5000...")
    print("Waiting for WhatsApp replies...")
    print("\nHow to reply to an email from WhatsApp:")
    print("  Type:  REPLY 1 Your message here")
    print("  This replies to email number 1 from the last agent run.\n")
    app.run(port=5000, debug=False)