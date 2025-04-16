import json
import os.path
import sqlite3
from datetime import datetime
from typing import List, Optional, Tuple

import requests
from supabase import Client

from . import utils
from ...db.models import Message, MessageContext, Contact, Chat


def get_sender_name(db: Client, sender_jid: str) -> str:
    try:
        response = (
            db.table("chats")
            .select("name")
            .eq("jid", sender_jid)
            .limit(1)
            .single()
            .execute()
        )

        if response.data:
            return response.data["name"]

        if "@" in sender_jid:
            phone_part = sender_jid.split("@")[0]
        else:
            phone_part = sender_jid

        response = (
            db.table("chats")
            .select("name")
            .ilike("jid", f"%{phone_part}%")
            .limit(1)
            .single()
            .execute()
        )

        return response.data["name"] if response.data else sender_jid

    except Exception as e:
        print(f"Database error while getting sender name: {e}")
        return sender_jid


def format_message(message: Message, show_chat_info: bool = True) -> None:
    """Print a single message with consistent formatting."""
    output = ""

    if show_chat_info and message.chat_name:
        output += f"[{message.timestamp:%Y-%m-%d %H:%M:%S}] Chat: {message.chat_name} "
    else:
        output += f"[{message.timestamp:%Y-%m-%d %H:%M:%S}] "

    content_prefix = ""
    if hasattr(message, "media_type") and message.media_type:
        content_prefix = f"[{message.media_type} - Message ID: {message.id} - Chat JID: {message.chat_jid}] "

    try:
        sender_name = (
            get_sender_name(message.sender) if not message.is_from_me else "Me"
        )
        output += f"From: {sender_name}: {content_prefix}{message.content}\n"
    except Exception as e:
        print(f"Error formatting message: {e}")
    return output


def format_messages_list(messages: List[Message], show_chat_info: bool = True) -> None:
    output = ""
    if not messages:
        output += "No messages to display."
        return output

    for message in messages:
        output += format_message(message, show_chat_info)
    return output


def list_messages(
    db: Client,
    after: Optional[str] = None,
    before: Optional[str] = None,
    sender_phone_number: Optional[str] = None,
    chat_jid: Optional[str] = None,
    query: Optional[str] = None,
    limit: int = 20,
    page: int = 0,
    include_context: bool = True,
    context_before: int = 1,
    context_after: int = 1,
) -> List[Message]:
    """Get messages matching the specified criteria with optional context."""
    try:
        query_builder = (
            db.table("messages")
            .select(
                "messages.timestamp, messages.sender, chats.name, messages.content, messages.is_from_me, chats.jid, messages.id, messages.media_type"
            )
            .join("chats", "messages.chat_jid=chats.jid")
        )

        # Add filters
        if after:
            try:
                after = datetime.fromisoformat(after)
            except ValueError:
                raise ValueError(
                    f"Invalid date format for 'after': {after}. Please use ISO-8601 format."
                )
            query_builder = query_builder.gt("messages.timestamp", after)

        if before:
            try:
                before = datetime.fromisoformat(before)
            except ValueError:
                raise ValueError(
                    f"Invalid date format for 'before': {before}. Please use ISO-8601 format."
                )
            query_builder = query_builder.lt("messages.timestamp", before)

        if sender_phone_number:
            query_builder = query_builder.eq("messages.sender", sender_phone_number)

        if chat_jid:
            query_builder = query_builder.eq("messages.chat_jid", chat_jid)

        if query:
            query_builder = query_builder.ilike("messages.content", f"%{query}%")

        # Add pagination and ordering
        offset = page * limit
        response = (
            query_builder.order("messages.timestamp", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )

        result = []
        for msg in response.data:
            message = Message(
                timestamp=datetime.fromisoformat(msg["timestamp"]),
                sender=msg["sender"],
                chat_name=msg["name"],
                content=msg["content"],
                is_from_me=msg["is_from_me"],
                chat_jid=msg["jid"],
                id=msg["id"],
                media_type=msg["media_type"],
            )
            result.append(message)

        if include_context and result:
            # Add context for each message
            messages_with_context = []
            for msg in result:
                context = get_message_context(msg.id, context_before, context_after)
                messages_with_context.extend(context.before)
                messages_with_context.append(context.message)
                messages_with_context.extend(context.after)

            return format_messages_list(messages_with_context, show_chat_info=True)

        # Format and display messages without context
        return format_messages_list(result, show_chat_info=True)

    except Exception as e:
        print(f"Database error: {e}")
        return []


def get_message_context(
    db: Client, message_id: str, before: int = 5, after: int = 5  # Add db parameter
) -> MessageContext:
    """Get context around a specific message."""
    try:
        # Get the target message first
        response = (
            db.table("messages")
            .select(
                "messages.timestamp, messages.sender, chats.name, messages.content, messages.is_from_me, chats.jid, messages.id, messages.chat_jid, messages.media_type"
            )
            .join("chats", "messages.chat_jid=chats.jid")
            .eq("messages.id", message_id)
            .single()
            .execute()
        )

        msg_data = response.data
        if not msg_data:
            raise ValueError(f"Message with ID {message_id} not found")

        target_message = Message(
            timestamp=datetime.fromisoformat(msg_data["timestamp"]),
            sender=msg_data["sender"],
            chat_name=msg_data["name"],
            content=msg_data["content"],
            is_from_me=msg_data["is_from_me"],
            chat_jid=msg_data["jid"],
            id=msg_data["id"],
            media_type=msg_data["media_type"],
        )

        # Get messages before
        before_response = (
            db.table("messages")
            .select(
                "messages.timestamp, messages.sender, chats.name, messages.content, messages.is_from_me, chats.jid, messages.id, messages.media_type"
            )
            .join("chats", "messages.chat_jid=chats.jid")
            .eq("messages.chat_jid", msg_data["chat_jid"])
            .lt("messages.timestamp", msg_data["timestamp"])
            .order("messages.timestamp", desc=True)
            .limit(before)
            .execute()
        )

        before_messages = []
        for msg in before_response.data:
            before_messages.append(
                Message(
                    timestamp=datetime.fromisoformat(msg["timestamp"]),
                    sender=msg["sender"],
                    chat_name=msg["name"],
                    content=msg["content"],
                    is_from_me=msg["is_from_me"],
                    chat_jid=msg["jid"],
                    id=msg["id"],
                    media_type=msg["media_type"],
                )
            )

        # Get messages after
        after_response = (
            db.table("messages")
            .select(
                "messages.timestamp, messages.sender, chats.name, messages.content, messages.is_from_me, chats.jid, messages.id, messages.media_type"
            )
            .join("chats", "messages.chat_jid=chats.jid")
            .eq("messages.chat_jid", msg_data["chat_jid"])
            .gt("messages.timestamp", msg_data["timestamp"])
            .order("messages.timestamp", asc=True)
            .limit(after)
            .execute()
        )

        after_messages = []
        for msg in after_response.data:
            after_messages.append(
                Message(
                    timestamp=datetime.fromisoformat(msg["timestamp"]),
                    sender=msg["sender"],
                    chat_name=msg["name"],
                    content=msg["content"],
                    is_from_me=msg["is_from_me"],
                    chat_jid=msg["jid"],
                    id=msg["id"],
                    media_type=msg["media_type"],
                )
            )

        return MessageContext(
            message=target_message, before=before_messages, after=after_messages
        )

    except Exception as e:
        print(f"Database error: {e}")
        raise


def list_chats(
    db: Client,  # Add db parameter
    query: Optional[str] = None,
    limit: int = 20,
    page: int = 0,
    include_last_message: bool = True,
    sort_by: str = "last_active",
) -> List[Chat]:
    """Get chats matching the specified criteria."""
    try:
        # Build base query
        query_builder = db.table("chats").select(
            """
                chats.jid,
                chats.name,
                chats.last_message_time,
                messages.content as last_message,
                messages.sender as last_sender,
                messages.is_from_me as last_is_from_me
            """
        )

        if include_last_message:
            query_builder = query_builder.join(
                "messages",
                "chats.jid=messages.chat_jid AND chats.last_message_time=messages.timestamp",
                join_type="left",
            )

        if query:
            query_builder = query_builder.or_(
                f"name.ilike.%{query}%,jid.ilike.%{query}%"
            )

        # Add sorting
        if sort_by == "last_active":
            query_builder = query_builder.order("last_message_time", desc=True)
        else:
            query_builder = query_builder.order("name")

        # Add pagination
        offset = page * limit
        response = query_builder.range(offset, offset + limit - 1).execute()

        result = []
        for chat_data in response.data:
            chat = Chat(
                jid=chat_data["jid"],
                name=chat_data["name"],
                last_message_time=(
                    datetime.fromisoformat(chat_data["last_message_time"])
                    if chat_data["last_message_time"]
                    else None
                ),
                last_message=chat_data["last_message"],
                last_sender=chat_data["last_sender"],
                last_is_from_me=chat_data["last_is_from_me"],
            )
            result.append(chat)

        return result

    except Exception as e:
        print(f"Database error: {e}")
        return []


def search_contacts(db: Client, query: str) -> List[Contact]:  # Add db parameter
    """Search contacts by name or phone number."""
    try:
        response = (
            db.table("chats")
            .select("DISTINCT jid, name")
            .or_(f"name.ilike.%{query}%,jid.ilike.%{query}%")
            .not_("jid", "like", "%@g.us")
            .order("name, jid")
            .limit(50)
            .execute()
        )

        result = []
        for contact_data in response.data:
            contact = Contact(
                phone_number=contact_data["jid"].split("@")[0],
                name=contact_data["name"],
                jid=contact_data["jid"],
            )
            result.append(contact)

        return result

    except Exception as e:
        print(f"Database error: {e}")
        return []


def get_contact_chats(
    db: Client, jid: str, limit: int = 20, page: int = 0  # Add db parameter
) -> List[Chat]:
    """Get all chats involving the contact.

    Args:
        jid: The contact's JID to search for
        limit: Maximum number of chats to return (default 20)
        page: Page number for pagination (default 0)
    """
    try:
        response = (
            db.table("chats")
            .select(
                """
                DISTINCT
                chats.jid,
                chats.name,
                chats.last_message_time,
                messages.content as last_message,
                messages.sender as last_sender,
                messages.is_from_me as last_is_from_me
            """
            )
            .join("messages", "chats.jid=messages.chat_jid")
            .or_(f"messages.sender.eq.{jid},chats.jid.eq.{jid}")
            .order("chats.last_message_time", desc=True)
            .range(page * limit, (page * limit) + limit - 1)
            .execute()
        )

        result = []
        for chat_data in response.data:
            chat = Chat(
                jid=chat_data["jid"],
                name=chat_data["name"],
                last_message_time=(
                    datetime.fromisoformat(chat_data["last_message_time"])
                    if chat_data["last_message_time"]
                    else None
                ),
                last_message=chat_data["last_message"],
                last_sender=chat_data["last_sender"],
                last_is_from_me=chat_data["last_is_from_me"],
            )
            result.append(chat)

        return result

    except Exception as e:
        print(f"Database error: {e}")
        return []


def get_last_interaction(db: Client, jid: str) -> str:  # Add db parameter
    """Get most recent message involving the contact."""
    try:
        response = (
            db.table("messages")
            .select(
                """
                messages.timestamp,
                messages.sender,
                chats.name,
                messages.content,
                messages.is_from_me,
                chats.jid,
                messages.id,
                messages.media_type
            """
            )
            .join("chats", "messages.chat_jid=chats.jid")
            .or_(f"messages.sender.eq.{jid},chats.jid.eq.{jid}")
            .order("messages.timestamp", desc=True)
            .limit(1)
            .single()
            .execute()
        )

        msg_data = response.data
        if not msg_data:
            return None

        message = Message(
            timestamp=datetime.fromisoformat(msg_data["timestamp"]),
            sender=msg_data["sender"],
            chat_name=msg_data["name"],
            content=msg_data["content"],
            is_from_me=msg_data["is_from_me"],
            chat_jid=msg_data["jid"],
            id=msg_data["id"],
            media_type=msg_data["media_type"],
        )

        return format_message(message)

    except Exception as e:
        print(f"Database error: {e}")
        return None


def get_chat(
    db: Client, chat_jid: str, include_last_message: bool = True  # Add db parameter
) -> Optional[Chat]:
    """Get chat metadata by JID."""
    try:
        query_builder = db.table("chats").select(
            """
                chats.jid,
                chats.name,
                chats.last_message_time,
                messages.content as last_message,
                messages.sender as last_sender,
                messages.is_from_me as last_is_from_me
            """
        )

        if include_last_message:
            query_builder = query_builder.join(
                "messages",
                "chats.jid=messages.chat_jid AND chats.last_message_time=messages.timestamp",
                join_type="left",
            )

        response = query_builder.eq("chats.jid", chat_jid).single().execute()

        if not response.data:
            return None

        chat_data = response.data
        return Chat(
            jid=chat_data["jid"],
            name=chat_data["name"],
            last_message_time=(
                datetime.fromisoformat(chat_data["last_message_time"])
                if chat_data["last_message_time"]
                else None
            ),
            last_message=chat_data["last_message"],
            last_sender=chat_data["last_sender"],
            last_is_from_me=chat_data["last_is_from_me"],
        )

    except Exception as e:
        print(f"Database error: {e}")
        return None


def get_direct_chat_by_contact(
    db: Client, sender_phone_number: str  # Add db parameter
) -> Optional[Chat]:
    """Get chat metadata by sender phone number."""
    try:
        response = (
            db.table("chats")
            .select(
                """
                chats.jid,
                chats.name,
                chats.last_message_time,
                messages.content as last_message,
                messages.sender as last_sender,
                messages.is_from_me as last_is_from_me
            """
            )
            .join(
                "messages",
                "chats.jid=messages.chat_jid AND chats.last_message_time=messages.timestamp",
                join_type="left",
            )
            .ilike("chats.jid", f"%{sender_phone_number}%")
            .not_("chats.jid", "like", "%@g.us")
            .limit(1)
            .single()
            .execute()
        )

        if not response.data:
            return None

        chat_data = response.data
        return Chat(
            jid=chat_data["jid"],
            name=chat_data["name"],
            last_message_time=(
                datetime.fromisoformat(chat_data["last_message_time"])
                if chat_data["last_message_time"]
                else None
            ),
            last_message=chat_data["last_message"],
            last_sender=chat_data["last_sender"],
            last_is_from_me=chat_data["last_is_from_me"],
        )

    except Exception as e:
        print(f"Database error: {e}")
        return None


def send_message(
    api_base_url: str, recipient: str, message: str  # Add API base URL parameter
) -> Tuple[bool, str]:
    try:
        # Validate input
        if not recipient:
            return False, "Recipient must be provided"

        url = f"{api_base_url}/send"
        payload = {
            "recipient": recipient,
            "message": message,
        }

        response = requests.post(url, json=payload)

        # Check if the request was successful
        if response.status_code == 200:
            result = response.json()
            return result.get("success", False), result.get(
                "message", "Unknown response"
            )
        else:
            return False, f"Error: HTTP {response.status_code} - {response.text}"

    except requests.RequestException as e:
        return False, f"Request error: {str(e)}"
    except json.JSONDecodeError:
        return False, f"Error parsing response: {response.text}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"


def send_file(
    api_base_url: str, recipient: str, media_path: str  # Add API base URL parameter
) -> Tuple[bool, str]:
    try:
        # Validate input
        if not recipient:
            return False, "Recipient must be provided"

        if not media_path:
            return False, "Media path must be provided"

        if not os.path.isfile(media_path):
            return False, f"Media file not found: {media_path}"

        url = f"{api_base_url}/send"
        payload = {"recipient": recipient, "media_path": media_path}

        response = requests.post(url, json=payload)

        # Check if the request was successful
        if response.status_code == 200:
            result = response.json()
            return result.get("success", False), result.get(
                "message", "Unknown response"
            )
        else:
            return False, f"Error: HTTP {response.status_code} - {response.text}"

    except requests.RequestException as e:
        return False, f"Request error: {str(e)}"
    except json.JSONDecodeError:
        return False, f"Error parsing response: {response.text}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"


def send_audio_message(
    api_base_url: str, recipient: str, media_path: str  # Add API base URL parameter
) -> Tuple[bool, str]:
    try:
        # Validate input
        if not recipient:
            return False, "Recipient must be provided"

        if not media_path:
            return False, "Media path must be provided"

        if not os.path.isfile(media_path):
            return False, f"Media file not found: {media_path}"

        if not media_path.endswith(".ogg"):
            try:
                media_path = utils.convert_to_opus_ogg_temp(media_path)
            except Exception as e:
                return (
                    False,
                    f"Error converting file to opus ogg. You likely need to install ffmpeg: {str(e)}",
                )

        url = f"{api_base_url}/send"
        payload = {"recipient": recipient, "media_path": media_path}

        response = requests.post(url, json=payload)

        # Check if the request was successful
        if response.status_code == 200:
            result = response.json()
            return result.get("success", False), result.get(
                "message", "Unknown response"
            )
        else:
            return False, f"Error: HTTP {response.status_code} - {response.text}"

    except requests.RequestException as e:
        return False, f"Request error: {str(e)}"
    except json.JSONDecodeError:
        return False, f"Error parsing response: {response.text}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"


def download_media(
    api_base_url: str, message_id: str, chat_jid: str  # Add API base URL parameter
) -> Optional[str]:
    """Download media from a message and return the local file path.

    Args:
        api_base_url: The base URL for the WhatsApp API
        message_id: The ID of the message containing the media
        chat_jid: The JID of the chat containing the message

    Returns:
        The local file path if download was successful, None otherwise
    """
    try:
        url = f"{api_base_url}/download"
        payload = {"message_id": message_id, "chat_jid": chat_jid}

        response = requests.post(url, json=payload)

        if response.status_code == 200:
            result = response.json()
            if result.get("success", False):
                path = result.get("path")
                print(f"Media downloaded successfully: {path}")
                return path
            else:
                print(f"Download failed: {result.get('message', 'Unknown error')}")
                return None
        else:
            print(f"Error: HTTP {response.status_code} - {response.text}")
            return None

    except requests.RequestException as e:
        print(f"Request error: {str(e)}")
        return None
    except json.JSONDecodeError:
        print(f"Error parsing response: {response.text}")
        return None
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return None
