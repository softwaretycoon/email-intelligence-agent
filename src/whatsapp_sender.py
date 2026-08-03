import os
from typing import cast
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

_account_sid = os.getenv("TWILIO_ACCOUNT_SID")
_auth_token  = os.getenv("TWILIO_AUTH_TOKEN")
_from_number = os.getenv("TWILIO_WHATSAPP_FROM")
_to_number   = os.getenv("TWILIO_WHATSAPP_TO")

if not all([_account_sid, _auth_token, _from_number, _to_number]):
    raise EnvironmentError(
        "Missing one or more Twilio env vars: "
        "TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM, TWILIO_WHATSAPP_TO"
    )

# Cast to str now that we've validated none of these are None -
# Pylance can't infer this narrowing once the variables are read inside a function.
account_sid = cast(str, _account_sid)
auth_token  = cast(str, _auth_token)
from_number = cast(str, _from_number)
to_number   = cast(str, _to_number)

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
    print(f"WhatsApp message sent - SID: {msg.sid}")
    return msg.sid


def send_all_summaries(summaries):
    """
    Sends each summary as a separate WhatsApp message.
    No header or footer - clean output only.
    """
    if not summaries:
        print("No summaries to send.")
        return

    for item in summaries:
        send_whatsapp(item['summary'])

    print(f"All {len(summaries)} summary/summaries delivered to WhatsApp.")


if __name__ == '__main__':
    print("Sending a test WhatsApp message...")
    send_whatsapp("Hello from your Email Intelligence Agent! WhatsApp connection is working perfectly.")
    print("Done - check your WhatsApp.")