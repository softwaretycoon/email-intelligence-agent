import os
import sys
import json
import time
import schedule
from datetime import datetime

# ── Add src folder to path ────────────────────────────────────────────────────
sys.path.append('src')

from email_reader    import get_unread_emails, get_gmail_service, mark_as_read
from summariser      import summarise_all_emails
from whatsapp_sender import send_all_summaries, send_whatsapp

# ── Context file path — shared with reply_handler.py ─────────────────────────
CONTEXT_FILE = 'email_context.json'


def update_email_context(email_id, sender, subject):
    """
    Saves email context to JSON file so reply_handler.py can read it.
    """
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

    # ── Step 1: Read unread emails ────────────────────────────────
    print("\n📧 Step 1: Reading unread emails from Gmail...")
    service = get_gmail_service()
    emails  = get_unread_emails(max_results=5, service=service)

    if not emails:
        print("✅ No new emails found. Agent going back to sleep.")
        return

    print(f"✅ Found {len(emails)} unread email(s).")

    # ── Step 2: Summarise with Gemini ─────────────────────────────
    print("\n🤖 Step 2: Summarising emails with Gemini...")
    summaries = summarise_all_emails(emails, priority_filter=True)
    print(f"✅ {len(summaries)} email(s) summarised.")

    if not summaries:
        print("No summaries to send — all emails were filtered out.")
        return

    # ── Step 3: Send to WhatsApp ──────────────────────────────────
    print("\n📱 Step 3: Sending summaries to WhatsApp...")
    send_all_summaries(summaries)
    print("✅ All summaries sent to WhatsApp.")

    # ── Step 4: Save email context for WhatsApp replies ──────────
    print("\n💾 Step 4: Saving email context for replies...")
    # Clear old context first so numbers stay consistent
    with open(CONTEXT_FILE, 'w') as f:
        json.dump({}, f)

    for email in emails:
        update_email_context(
            email_id=email['id'],
            sender=email['sender'],
            subject=email['subject']
        )
    print(f"✅ Context saved for {len(emails)} email(s).")

    # ── Step 5: Mark emails as read ───────────────────────────────
    print("\n✅ Step 5: Marking emails as read in Gmail...")
    for email in emails:
        mark_as_read(service, email['id'])
    print(f"✅ {len(emails)} email(s) marked as read.")

    print(f"\n🎉 Agent completed at {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}")


def start_agent():
    """
    Starts the agent and schedules it to run every 30 minutes.
    Also runs immediately on startup.
    """
    print("🚀 Email Intelligence Agent starting...")
    print("📬 Powered by Gmail + Gemini + WhatsApp")
    print("⏰ Will check for new emails every 30 minutes")
    print("Press Ctrl+C to stop the agent.\n")
    # Run immediately on startup
    run_agent()

    # Then schedule to run every 30 minutes
    schedule.every(30).minutes.do(run_agent)

    # Keep the agent alive
    while True:
        schedule.run_pending()
        time.sleep(60)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    try:
        start_agent()
    except KeyboardInterrupt:
        print("\n\n🛑 Agent stopped by user.")
        send_whatsapp("🛑 *Email Intelligence Agent has been stopped.*")
        print("Goodbye!")