import os
import sqlite3
from openai import OpenAI
from temporalio import activity
from datetime import datetime, timedelta
import whatsapp

# Configure LM Studio with specific network IP and API Token
# Provided by user: http://192.168.1.32:1234
LM_STUDIO_URL = "http://192.168.1.32:1234/v1"
LM_STUDIO_API_KEY = "sk-lm-2XurZEk6:gvRNAvdVPQAar17ts9xg"

client = OpenAI(base_url=LM_STUDIO_URL, api_key=LM_STUDIO_API_KEY)

@activity.defn
async def check_for_new_messages() -> list[dict]:
    \"\"\"
    Checks the database for chats where the last message is NOT from me.
    Returns a list of chat JIDs that need a reply.
    \"\"\"
    chats = whatsapp.list_chats(limit=50, include_last_message=True)
    needs_reply = []
    
    for chat in chats:
        # If the last message is NOT from me and it's within the last hour
        if chat.last_is_from_me is False:
            if chat.last_message_time and chat.last_message_time > datetime.now() - timedelta(hours=1):
                needs_reply.append({
                    "jid": chat.jid,
                    "name": chat.name,
                    "last_message": chat.last_message
                })
    
    return needs_reply

@activity.defn
async def generate_bespoke_reply(chat_info: dict) -> str:
    \"\"\"
    Uses LM Studio to generate a reply based on the last message.
    \"\"\"
    try:
        prompt = f\"\"\"
        You are an automated assistant for a WhatsApp user named {chat_info.get('name', 'User')}.
        The last message received was: "{chat_info['last_message']}"
        
        Task: Write a helpful, professional, and bespoke reply. 
        Keep it concise and conversational (it's WhatsApp).
        Do not use placeholders like [Your Name].
        \"\"\"
        
        # LM Studio handles the model selection in its UI, so 'local-model' is a generic identifier
        response = client.chat.completions.create(
            model="local-model", 
            messages=[
                {"role": "system", "content": "You are a helpful WhatsApp assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        activity.logger.error(f"LM Studio Error at {LM_STUDIO_URL}: {str(e)}")
        return f"System: Failed to generate reply via LM Studio. Is the server at {LM_STUDIO_URL} running? {str(e)}"

@activity.defn
async def send_reply(jid: str, text: str) -> bool:
    \"\"\"
    Sends the generated message via the WhatsApp bridge.
    \"\"\"
    success, message = whatsapp.send_message(jid, text)
    if not success:
        activity.logger.error(f"Failed to send message to {jid}: {message}")
    return success
