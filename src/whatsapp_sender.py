import os
from twilio.rest import Client
from dotenv import load_dotenv

# ── Load credentials from .env file ──────────────────────────────────────────
load_dotenv()

# ── Connect to Twilio ─────────────────────────────────────────────────────────
account_sid = os.getenv("TWILIO_ACCOUNT_SID") or ""
auth_token  = os.getenv("TWILIO_AUTH_TOKEN") or ""
from_number = os.getenv("TWILIO_WHATSAPP_FROM") or ""
to_number   = os.getenv("TWILIO_WHATSAPP_TO") or ""

client = Client(account_sid, auth_token)


def send_whatsapp(message):
    """
    Sends a single WhatsApp message via Twilio sandbox.
    """
    msg = client.messages.create(
        from_=from_number,
        to=to_number,
        body=message
    )
    print(f"WhatsApp message sent — SID: {msg.sid}")
    return msg.sid


def send_all_summaries(summaries):
    """
    Takes a list of summaries and sends each one
    as a separate WhatsApp message.
    """
    if not summaries:
        print("No summaries to send.")
        return

    # Send a header message first
    header = (
    f"📬 *Email Intelligence Agent*\n\n"
    f"You have *{len(summaries)} important email(s)* to review:\n"
    f"_(Low priority emails have been filtered out)_\n"
    f"{'─'*30}"
)

    # Send each summary as its own message
    for i, item in enumerate(summaries, 1):
        message = f"*Email {i} of {len(summaries)}*\n\n{item['summary']}"
        send_whatsapp(message)
        print(f"Sent summary {i} of {len(summaries)} to WhatsApp.")



# ── Test this file directly ───────────────────────────────────────────────────
if __name__ == '__main__':
    print("Sending a test WhatsApp message...")
    send_whatsapp("👋 Hello from your Email Intelligence Agent! WhatsApp connection is working perfectly.")
    print("Done — check your WhatsApp.")