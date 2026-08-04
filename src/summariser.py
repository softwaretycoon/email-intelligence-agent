import os
import time
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

SKIP_KEYWORDS = [
    'unsubscribe', 'newsletter', 'promotion', 'offer',
    'deal', 'discount', 'sale', 'marketing', 'no-reply',
    'noreply', 'donotreply', 'do-not-reply', 'notification',
    'automated', 'auto-generated', 'mailer-daemon'
]


def is_newsletter(sender, subject, body):
    combined = (sender + ' ' + subject + ' ' + body[:500]).lower()
    return any(kw in combined for kw in SKIP_KEYWORDS)


def _extract_text(response):
    """Safely extract text from a Gemini response, guarding against None."""
    text = response.text
    if text is None:
        raise ValueError("Gemini returned an empty response (no text).")
    return text.strip()


def summarise_single_email(sender, subject, body):
    """
    Sends one email to Gemini and returns a structured summary.
    """
    prompt = (
    "You are an intelligent email assistant.\n"
    "Summarise the email below in 3-4 sentences maximum.\n"
    "Be clear, concise and professional.\n"
    "Format the output for WhatsApp using *asterisks* for bold labels only (not the values).\n\n"
    "Email Details:\n"
    f"- From:    {sender}\n"
    f"- Subject: {subject}\n"
    f"- Body:    {body}\n\n"
    "Return your summary in this exact format:\n"
    "*From:* [sender name]\n"
    "*Email:* [sender email address]\n"
    "*Subject:* [subject]\n\n"
    "*Summary:* [3-4 sentence summary]\n\n"
    "*Action needed:* [Yes / No - and what action if yes]\n"
    "*Urgency:* [Low / Medium / High]\n"
)

    try:
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt
        )
        return _extract_text(response)

    except Exception as e:
        if '429' in str(e):
            print("  Rate limit hit - waiting 60 seconds...")
            time.sleep(60)
            response = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=prompt
            )
            return _extract_text(response)
        else:
            raise e


def needs_attention(summary):
    """
    Returns True only if the email requires action or is Medium/High urgency.
    Low urgency emails with no action needed are silently skipped.
    """
    summary_lower = summary.lower()

    # Check urgency
    is_high    = "urgency: high"   in summary_lower
    is_medium  = "urgency: medium" in summary_lower
    is_low     = "urgency: low"    in summary_lower

    # Check action needed
    action_yes = "action needed: yes" in summary_lower

    # Only send if action is needed OR urgency is Medium or High
    if action_yes or is_high or is_medium:
        return True

    print("  Skipping - Low urgency, no action needed.")
    return False


def process_incoming_email(email):
    """
    Processes a single incoming email.
    Returns the summary string or None if the email should be skipped.
    """
    sender  = email.get('sender', '')
    subject = email.get('subject', '')
    body    = email.get('body', '')

    # Skip newsletters
    if is_newsletter(sender, subject, body):
        print(f"  Skipping - newsletter or promotional email")
        return None

    # Summarise with Gemini
    print(f"  Summarising email from {sender}...")
    summary = summarise_single_email(sender, subject, body)

    # Skip low urgency emails with no action needed
    if not needs_attention(summary):
        return None

    print(f"  Summary ready - sending to WhatsApp.")
    return summary


def summarise_all_emails(emails, priority_filter=True):
    """Legacy function kept for compatibility."""
    summaries = []
    skipped   = 0

    for email in emails:
        summary = process_incoming_email(email)

        if summary is None:
            skipped += 1
            continue

        urgency = "Low"
        if "urgency: high"   in summary.lower(): urgency = "High"
        elif "urgency: medium" in summary.lower(): urgency = "Medium"

        summaries.append({
            'id':      email['id'],
            'summary': summary,
            'urgency': urgency
        })

    if skipped > 0:
        print(f"  {skipped} email(s) skipped.")

    return summaries


if __name__ == '__main__':
    import sys
    sys.path.append('src')
    from email_reader import get_unread_emails

    print("Reading latest email from Gmail...")
    emails = get_unread_emails(max_results=1)

    if not emails:
        print("No unread emails.")
    else:
        summary = process_incoming_email(emails[0])
        if summary:
            print("\n" + "="*60)
            print(summary)
        else:
            print("Email was filtered out.")