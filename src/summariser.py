import os
import time
from google import genai
from dotenv import load_dotenv

# ── Load credentials from .env file ──────────────────────────────────────────
load_dotenv()

# ── Connect to Gemini ─────────────────────────────────────────────────────────
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def summarise_email(sender, subject, body):
    """
    Sends one email to Gemini and gets back a short summary.
    Returns a clean, readable summary string.
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

    response = client.models.generate_content(
        model="gemini-1.5-flash-8b",
        contents=prompt
    )
    return response.text.strip()


def summarise_all_emails(emails, priority_filter=True):
    """
    Takes a list of emails from email_reader.py
    and returns a list of summaries.
    If priority_filter is True, skips newsletters and promotions.
    """
    summaries = []
    skipped   = 0

    # Keywords that indicate newsletters / promotions
    skip_keywords = [
        'unsubscribe', 'newsletter', 'promotion', 'offer',
        'deal', 'discount', 'sale', 'marketing', 'no-reply'
    ]

    for i, email in enumerate(emails, 1):
        print(f"Summarising email {i} of {len(emails)}...")

        # ── Check for newsletter before calling Gemini ────────────
        sender_lower  = email['sender'].lower()
        subject_lower = email['subject'].lower()
        body_lower    = email['body'].lower()

        is_newsletter = any(
            kw in sender_lower or kw in subject_lower or kw in body_lower
            for kw in skip_keywords
        )

        if priority_filter and is_newsletter:
            print(f"  ⏭ Skipping — newsletter or promotional email")
            skipped += 1
            continue

        # ── Call Gemini with rate limit protection ────────────────
        try:
            summary = summarise_email(
                sender=email['sender'],
                subject=email['subject'],
                body=email['body']
            )
        except Exception as e:
            if '429' in str(e):
                print(f"  ⏳ Rate limit hit — waiting 20 seconds...")
                time.sleep(20)
                # Retry once after waiting
                summary = summarise_email(
                    sender=email['sender'],
                    subject=email['subject'],
                    body=email['body']
                )
            else:
                print(f"  ❌ Error summarising email: {e}")
                continue

        # ── Extract urgency from the summary ──────────────────────
        urgency = "Low"
        if "Urgency: High"   in summary: urgency = "High"
        elif "Urgency: Medium" in summary: urgency = "Medium"
        elif "Urgency: Low"   in summary: urgency = "Low"

        summaries.append({
            'id':      email['id'],
            'summary': summary,
            'urgency': urgency
        })

        # ── Wait 5 seconds between each Gemini call ───────────────
        # This keeps us well within the 15 requests/minute limit
        if i < len(emails):
            print(f"  ⏳ Waiting 5 seconds before next email...")
            time.sleep(5)

    print(f"\n✅ {len(summaries)} email(s) passed the priority filter.")
    if skipped > 0:
        print(f"⏭  {skipped} newsletter/promotional email(s) skipped.")

    return summaries


# ── Test this file directly ───────────────────────────────────────────────────
if __name__ == '__main__':
    import sys
    sys.path.append('src')
    from email_reader import get_unread_emails

    print("Reading emails from Gmail...")
    emails = get_unread_emails(max_results=3)

    if not emails:
        print("No unread emails to summarise.")
    else:
        print(f"\nSummarising {len(emails)} email(s) with Gemini...\n")
        summaries = summarise_all_emails(emails)

        for s in summaries:
            print("\n" + "="*60)
            print(s['summary'])