import os
import time
from google import genai
from dotenv import load_dotenv

# ── Load credentials from .env file ──────────────────────────────────────────
load_dotenv()

# ── Connect to Gemini ─────────────────────────────────────────────────────────
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# ── Newsletter keywords — skip these without calling Gemini ──────────────────
SKIP_KEYWORDS = [
    'unsubscribe', 'newsletter', 'promotion', 'offer',
    'deal', 'discount', 'sale', 'marketing', 'no-reply',
    'noreply', 'donotreply', 'do-not-reply', 'notification',
    'automated', 'auto-generated', 'mailer-daemon'
]


def is_newsletter(sender, subject, body):
    """
    Returns True if the email looks like a newsletter or promotion.
    Checks sender, subject and first 500 chars of body.
    """
    combined = (sender + ' ' + subject + ' ' + body[:500]).lower()
    return any(kw in combined for kw in SKIP_KEYWORDS)


def summarise_single_email(sender, subject, body):
    """
    Sends one email to Gemini and returns a structured summary.
    Called once per email as it arrives — no batching.
    """
    prompt = f"""
You are an intelligent email assistant.
Summarise the email below in 3-4 sentences maximum.
Be clear, concise and professional.
Highlight the key point, any action required, and the urgency level.

Email Details:
- From:    {sender}
- Subject: {subject}
- Body:    {body}

Return your summary in this exact format:
📧 From: [sender name only, not full email]
📌 Subject: [subject]
📝 Summary: [your 3-4 sentence summary]
⚡ Action needed: [Yes / No — and what action if yes]
🔴 Urgency: [Low / Medium / High]
"""
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt
        )
        return response.text.strip()

    except Exception as e:
        if '429' in str(e):
            print("  \u23F3 Rate limit hit \u2014 waiting 60 seconds...")
            time.sleep(60)
            # Retry once
            response = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt
            )
            return response.text.strip()
        else:
            raise e


def process_incoming_email(email):
    """
    Processes a single incoming email.
    Called directly from main.py when a new email arrives via Pub/Sub.
    Returns the summary string or None if the email should be skipped.
    """
    sender  = email.get('sender', '')
    subject = email.get('subject', '')
    body    = email.get('body', '')

    # ── Check if newsletter before calling Gemini ─────────────────
    if is_newsletter(sender, subject, body):
        print(f"  \u23ED Skipping \u2014 newsletter or promotional email")
        return None

    # ── Summarise with Gemini ─────────────────────────────────────
    print(f"  \uD83E\uDD16 Summarising email from {sender}...")
    summary = summarise_single_email(sender, subject, body)
    print(f"  \u2705 Summary ready.")
    return summary


def summarise_all_emails(emails, priority_filter=True):
    """
    Legacy function kept for compatibility with startup check.
    Processes a list of emails one at a time.
    """
    summaries = []
    skipped   = 0

    for email in emails:
        summary = process_incoming_email(email)

        if summary is None:
            skipped += 1
            continue

        # Extract urgency from summary
        urgency = "Low"
        if "Urgency: High"   in summary: urgency = "High"
        elif "Urgency: Medium" in summary: urgency = "Medium"

        summaries.append({
            'id':      email['id'],
            'summary': summary,
            'urgency': urgency
        })

    if skipped > 0:
        print(f"\u23ED  {skipped} newsletter/promotional email(s) skipped.")

    return summaries


# ── Test this file directly ───────────────────────────────────────────────────
if __name__ == '__main__':
    import sys
    sys.path.append('src')
    from email_reader import get_unread_emails

    print("Reading latest email from Gmail...")
    emails = get_unread_emails(max_results=1)

    if not emails:
        print("No unread emails.")
    else:
        email   = emails[0]
        summary = process_incoming_email(email)
        if summary:
            print("\n" + "="*60)
            print(summary)
        else:
            print("Email was filtered out.")