import os
import sys
import json
import time
import base64
import schedule
import threading
from datetime import datetime
from flask import Flask, request

# ── Add src folder to path ────────────────────────────────────────────────────
sys.path.append('src')

from email_reader    import get_unread_emails, get_gmail_service, mark_as_read
from summariser      import summarise_all_emails
from whatsapp_sender import send_all_summaries, send_whatsapp

# ── Flask app for receiving Gmail push notifications ──────────────────────────
app = Flask(__name__)

# ── Context file path ─────────────────────────────────────────────────────────
CONTEXT_FILE = 'email_context.json'

# ── Track last processed history ID to avoid duplicate processing ─────────────
last_history_id = None


def update_email_context(email_id, sender, subject):
    """Saves email context to JSON file so reply_handler.py can read it."""
    context = {}
    if os.path.exists(CONTEXT_FILE):
        with open(CONTEXT_FILE, 'r') as f:
            context = json.load(f)

    context[email_id] = {
        'sender':  sender,
        'subject': subject
    }

    with open(CONTEXT_FILE, 'w') as f:
        json.dump(context, f, indent=2)

    print(f"Context saved for email from {sender}")


def run_agent():
    """
    Main agent function — runs the full pipeline:
    1. Read unread emails from Gmail
    2. Summarise each email with Gemini
    3. Send summaries to WhatsApp
    4. Save email context for replies
    5. Mark each email as read
    """
    print(f"\n{'='*60}")
    print(f"Agent running at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    try:
        # ── Step 1: Read unread emails ────────────────────────────
        print("\n📧 Step 1: Reading unread emails from Gmail...")
        service = get_gmail_service()
        emails  = get_unread_emails(max_results=5, service=service)

        if not emails:
            print("✅ No new emails found.")
            return

        print(f"✅ Found {len(emails)} unread email(s).")

        # ── Step 2: Summarise with Gemini ─────────────────────────
        print("\n🤖 Step 2: Summarising emails with Gemini...")
        summaries = summarise_all_emails(emails, priority_filter=True)
        print(f"✅ {len(summaries)} email(s) summarised.")

        if not summaries:
            print("No summaries to send — all emails were filtered out.")
            # Still mark as read
            for email in emails:
                mark_as_read(service, email['id'])
            return

        # ── Step 3: Send to WhatsApp ──────────────────────────────
        print("\n📱 Step 3: Sending summaries to WhatsApp...")
        send_all_summaries(summaries)
        print("✅ All summaries sent to WhatsApp.")

        # ── Step 4: Save email context for WhatsApp replies ───────
        print("\n💾 Step 4: Saving email context for replies...")
        with open(CONTEXT_FILE, 'w') as f:
            json.dump({}, f)

        for email in emails:
            update_email_context(
                email_id=email['id'],
                sender=email['sender'],
                subject=email['subject']
            )
        print(f"✅ Context saved for {len(emails)} email(s).")

        # ── Step 5: Mark emails as read ───────────────────────────
        print("\n✅ Step 5: Marking emails as read in Gmail...")
        for email in emails:
            mark_as_read(service, email['id'])
        print(f"✅ {len(emails)} email(s) marked as read.")

        print(f"\n🎉 Agent completed at {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'='*60}")

    except Exception as e:
        print(f"❌ Agent error: {e}")


# ── Gmail Push Notification Webhook ──────────────────────────────────────────
@app.route('/gmail-notification', methods=['POST'])
def gmail_notification():
    """
    Receives Gmail push notifications via Google Pub/Sub.
    Fires instantly when a new email arrives in the inbox.
    """
    global last_history_id

    try:
        # Decode the Pub/Sub message
        envelope = request.get_json()
        if not envelope or 'message' not in envelope:
            print("Invalid Pub/Sub message received.")
            return "OK", 200

        message     = envelope['message']
        data        = base64.b64decode(message['data']).decode('utf-8')
        notification = json.loads(data)

        history_id  = notification.get('historyId')
        email_addr  = notification.get('emailAddress')

        print(f"\n📬 New email notification received!")
        print(f"Email: {email_addr}")
        print(f"History ID: {history_id}")

        # Avoid processing the same notification twice
        if history_id == last_history_id:
            print("Duplicate notification — skipping.")
            return "OK", 200

        last_history_id = history_id

        # Run the agent in a background thread so webhook returns quickly
        thread = threading.Thread(target=run_agent)
        thread.daemon = True
        thread.start()

    except Exception as e:
        print(f"❌ Webhook error: {e}")

    return "OK", 200


# ── Health check endpoint ─────────────────────────────────────────────────────
@app.route('/health', methods=['GET'])
def health():
    return {"status": "running", "agent": "Email Intelligence Agent"}, 200


# ── Renew Gmail watch every 6 days (expires after 7 days) ────────────────────
def renew_gmail_watch():
    """Renews the Gmail push notification watch."""
    try:
        from gmail_watch import start_gmail_watch
        start_gmail_watch()
        print("✅ Gmail watch renewed successfully.")
    except Exception as e:
        print(f"❌ Failed to renew Gmail watch: {e}")


def start_agent():
    """
    Starts the agent:
    1. Sends startup WhatsApp notification
    2. Starts Gmail watch for push notifications
    3. Schedules watch renewal every 6 days
    4. Starts Flask server to receive notifications
    """
    print("🚀 Email Intelligence Agent starting...")
    print("📬 Powered by Gmail + Gemini + WhatsApp")
    print("⚡ Real-time mode — fires on every new email\n")


    # Start Gmail watch
    print("👀 Starting Gmail push notifications...")
    renew_gmail_watch()

    # Schedule watch renewal every 6 days
    schedule.every(6).days.do(renew_gmail_watch)

    # Run scheduler in background thread
    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(3600)  # check every hour

    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()

    # Run initial email check on startup
    run_agent()

    # Start Flask server — listens for Gmail push notifications
    print("\n🌐 Starting webhook server on port 5000...")
    app.run(host='0.0.0.0', port=5000, debug=False)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    try:
        start_agent()
    except KeyboardInterrupt:
        print("\n\n🛑 Agent stopped by user.")
        send_whatsapp("🛑 *Email Intelligence Agent has been stopped.*")
        print("Goodbye!")