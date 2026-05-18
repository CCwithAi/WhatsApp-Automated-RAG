# API Routes (MCP Tools)

This document lists all the tools (endpoints) exposed by the WhatsApp MCP server.

## MCP Tools

### Contact Management

- `search_contacts(query: str)`: Search for contacts by name or phone number.
- `get_chat(chat_jid: str)`: Get WhatsApp chat metadata by JID.
- `get_direct_chat_by_contact(sender_phone_number: str)`: Get WhatsApp chat metadata by phone number.
- `get_contact_chats(jid: str)`: Get all WhatsApp chats involving a specific contact.

### Messaging

- `send_message(recipient: str, message: str)`: Send a text message to a phone number or group JID.
- `list_messages(...)`: Retrieve messages with filters (date, sender, query, etc.).
- `get_last_interaction(jid: str)`: Get the most recent message with a contact.
- `get_message_context(message_id: str)`: Get surrounding messages for context.

### Media Handling

- `send_file(recipient: str, media_path: str)`: Send images, videos, or documents.
- `send_audio_message(recipient: str, media_path: str)`: Send audio as a WhatsApp voice message (requires FFmpeg for conversion).
- `download_media(message_id: str, chat_jid: str)`: Download media from a message to a local file.

### Chat List

- `list_chats(query, limit, page, ...)`: List and filter active chats.

## Internal Bridge API

The Go bridge exposes a private REST API on `http://localhost:8080` used by the Python MCP server to communicate with WhatsApp.
