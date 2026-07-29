import os
import sys
import json
import time
import base64
import schedule
import threading
from datetime import datetime
from flask import Flask, request

sys.path.append('src')

from email_reader    import get_gmail_service, mark_as_read, extract_body
from summariser      import process_incoming_email
from whatsapp_sender import send_whatsapp

app = Flask(__name__)

CONTEXT_FILE = 'email_context.json'
last_history_id = None


def update_email_context(email_id, sender, subject):
    context = {}
    if os.path.exists(CONTEXT_FILE):
        with open(CONTEXT_FILE, 'r') as f:
            context = json.load(f)
    context[email_id] = {'sender': sender, 'subject': subject}
    with open(CONTEXT_FILE, 'w') as f:
        json.dump(context, f, indent=2)
    print(f"Context saved for email from {sender}")


def run_agent_for_new_email(history_id):
    """
    Processes only the single latest email that triggered the notification.
    Skips low urgency emails with no action needed.
    """
    print(f"\n{'='*60}")
    print(f"New email received at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    try:
        service = get_gmail_service()

        # ── Get only the new message from Gmail history ───────────
        history = service.users().history().list(
            userId='me',
            startHistoryId=history_id,
            historyTypes=['messageAdded'],
            labelId='INBOX'
        ).execute()

        changes = history.get('history', [])

        if not changes:
            print("No new messages in history.")
            return

        # ── Get only the LATEST new email ID ──────────────────────
        new_message_ids = []
        for change in changes:
            for msg in change.get('messagesAdded', []):
                new_message_ids.append(msg['message']['id'])

        if not new_message_ids:
            print("No new inbox messages.")
            return

        # Take only the most recent one
        latest_id = new_message_ids[-1]
        print(f"Processing latest email ID: {latest_id}")

        # ── Fetch full email details ──────────────────────────────
        msg_data = service.users().messages().get(
            userId='me',
            id=latest_id,
            format='full'
        ).execute()

        headers = msg_data['payload']['headers']
        sender  = next((h['value'] for h in headers if h['name'] == 'From'),    'Unknown')
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        date    = next((h['value'] for h in headers if h['name'] == 'Date'),    'Unknown')
        body    = extract_body(msg_data['payload'])

        email = {
            'id':      latest_id,
            'sender':  sender,
            'subject': subject,
            'date':    date,
            'body':    body[:3000]
        }

        print(f"From:    {sender}")
        print(f"Subject: {subject}")

        # ── Summarise the single email ────────────────────────────
        summary = process_incoming_email(email)

        if summary is None:
            print("Email skipped - not actionable or newsletter.")
            mark_as_read(service, latest_id)
            return

        # ── Send to WhatsApp ──────────────────────────────────────
        print("Sending summary to WhatsApp...")
        message = f"*New Email Summary*\n\n{summary}"
        send_whatsapp(message)
        print("Summary sent to WhatsApp.")

        # ── Save context for reply feature ────────────────────────
        with open(CONTEXT_FILE, 'w') as f:
            json.dump({}, f)
        update_email_context(latest_id, sender, subject)

        # ── Mark as read ──────────────────────────────────────────
        mark_as_read(service, latest_id)

        print(f"Done at {datetime.now().strftime('%H:%M:%S')}")

    except Exception as e:
        print(f"Agent error: {e}")


@app.route('/gmail-notification', methods=['POST'])
def gmail_notification():
    global last_history_id

    try:
        envelope = request.get_json()
        if not envelope or 'message' not in envelope:
            return "OK", 200

        message      = envelope['message']
        data         = base64.b64decode(message['data']).decode('utf-8')
        notification = json.loads(data)

        history_id = notification.get('historyId')
        email_addr = notification.get('emailAddress')

        print(f"\nNew email notification - {email_addr} - History ID: {history_id}")

        if history_id == last_history_id:
            print("Duplicate notification - skipping.")
            return "OK", 200

        last_history_id = history_id

        thread = threading.Thread(
            target=run_agent_for_new_email,
            args=(history_id,)
        )
        thread.daemon = True
        thread.start()

    except Exception as e:
        print(f"Webhook error: {e}")

    return "OK", 200


@app.route('/whatsapp-reply', methods=['POST'])
def whatsapp_reply():
    """Handles WhatsApp replies and sends them via Gmail."""
    incoming_msg = request.form.get('Body', '').strip()
    print(f"Incoming WhatsApp message: {incoming_msg}")

    if not incoming_msg.upper().startswith('REPLY'):
        return "OK", 200

    parts = incoming_msg.split(' ', 2)
    if len(parts) < 3:
        return "OK", 200

    try:
        email_num  = int(parts[1])
        reply_body = parts[2]
    except ValueError:
        return "OK", 200

    try:
        context    = json.load(open(CONTEXT_FILE)) if os.path.exists(CONTEXT_FILE) else {}
        email_keys = list(context.keys())

        if not email_keys or email_num - 1 >= len(email_keys):
            print("No email context found.")
            return "OK", 200

        email_id  = email_keys[email_num - 1]
        email_ctx = context[email_id]

        from reply_handler import send_gmail_reply
        send_gmail_reply(
            to_email=email_ctx['sender'],
            subject=email_ctx['subject'],
            body=reply_body
        )

        send_whatsapp(
            f"Reply sent to: {email_ctx['sender']}\n"
            f"Subject: Re: {email_ctx['subject']}\n"
            f"Message: {reply_body}"
        )
        print(f"Reply sent to {email_ctx['sender']}")

    except Exception as e:
        print(f"Reply error: {e}")

    return "OK", 200


@app.route('/health', methods=['GET'])
def health():
    return {"status": "running", "agent": "Email Intelligence Agent"}, 200


def renew_gmail_watch():
    try:
        from gmail_watch import start_gmail_watch
        start_gmail_watch()
        print("Gmail watch renewed successfully.")
    except Exception as e:
        print(f"Failed to renew Gmail watch: {e}")


def start_agent():
    print("Email Intelligence Agent starting...")
    print("Real-time mode - fires on every new actionable email\n")

    send_whatsapp(
        "*Email Intelligence Agent is running!*\n\n"
        "I will summarise actionable emails instantly as they arrive.\n"
        "Low urgency emails with no action needed will be skipped.\n\n"
        "To reply: REPLY 1 Your message here"
    )

    print("Starting Gmail push notifications...")
    renew_gmail_watch()

    schedule.every(6).days.do(renew_gmail_watch)

    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(3600)

    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()

    print("Starting webhook server on port 5000...")
    app.run(host='0.0.0.0', port=5000, debug=False)


if __name__ == '__main__':
    try:
        start_agent()
    except KeyboardInterrupt:
        print("\nAgent stopped by user.")
        send_whatsapp("Email Intelligence Agent has been stopped.")
        print("Goodbye!")