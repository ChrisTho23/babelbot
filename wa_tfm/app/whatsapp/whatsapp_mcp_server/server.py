from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP
from . import whatsapp_tools
from supabase import Client
import os
from dotenv import load_dotenv

load_dotenv()


class WhatsAppMCPServer:
    def __init__(self, db: Client):
        self.db = db
        self.mcp = FastMCP("whatsapp")
        self.api_base_url = os.getenv(
            "WHATSAPP_API_BASE_URL", "http://localhost:8080/api"
        )
        self._setup_tools()

    def _setup_tools(self):
        @self.mcp.tool()
        def search_contacts(query: str) -> List[Dict[str, Any]]:
            """Search WhatsApp contacts by name or phone number.

            Args:
                query: Search term to match against contact names or phone numbers
            """
            contacts = whatsapp_tools.search_contacts(self.db, query)
            return contacts

        @self.mcp.tool()
        def list_messages(
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
        ) -> List[Dict[str, Any]]:
            """Get WhatsApp messages matching specified criteria with optional context.

            Args:
                after: Optional ISO-8601 formatted string to only return messages after this date
                before: Optional ISO-8601 formatted string to only return messages before this date
                sender_phone_number: Optional phone number to filter messages by sender
                chat_jid: Optional chat JID to filter messages by chat
                query: Optional search term to filter messages by content
                limit: Maximum number of messages to return (default 20)
                page: Page number for pagination (default 0)
                include_context: Whether to include messages before and after matches (default True)
                context_before: Number of messages to include before each match (default 1)
                context_after: Number of messages to include after each match (default 1)
            """
            messages = whatsapp_tools.list_messages(
                db=self.db,
                after=after,
                before=before,
                sender_phone_number=sender_phone_number,
                chat_jid=chat_jid,
                query=query,
                limit=limit,
                page=page,
                include_context=include_context,
                context_before=context_before,
                context_after=context_after,
            )
            return messages

        @self.mcp.tool()
        def list_chats(
            query: Optional[str] = None,
            limit: int = 20,
            page: int = 0,
            include_last_message: bool = True,
            sort_by: str = "last_active",
        ) -> List[Dict[str, Any]]:
            """Get WhatsApp chats matching specified criteria.

            Args:
                query: Optional search term to filter chats by name or JID
                limit: Maximum number of chats to return (default 20)
                page: Page number for pagination (default 0)
                include_last_message: Whether to include the last message in each chat (default True)
                sort_by: Field to sort results by, either "last_active" or "name" (default "last_active")
            """
            chats = whatsapp_tools.list_chats(
                db=self.db,
                query=query,
                limit=limit,
                page=page,
                include_last_message=include_last_message,
                sort_by=sort_by,
            )
            return chats

        @self.mcp.tool()
        def get_chat(
            chat_jid: str, include_last_message: bool = True
        ) -> Dict[str, Any]:
            """Get WhatsApp chat metadata by JID.

            Args:
                chat_jid: The JID of the chat to retrieve
                include_last_message: Whether to include the last message (default True)
            """
            chat = whatsapp_tools.get_chat(self.db, chat_jid, include_last_message)
            return chat

        @self.mcp.tool()
        def get_direct_chat_by_contact(sender_phone_number: str) -> Dict[str, Any]:
            """Get WhatsApp chat metadata by sender phone number.

            Args:
                sender_phone_number: The phone number to search for
            """
            chat = whatsapp_tools.get_direct_chat_by_contact(
                self.db, sender_phone_number
            )
            return chat

        @self.mcp.tool()
        def get_contact_chats(
            jid: str, limit: int = 20, page: int = 0
        ) -> List[Dict[str, Any]]:
            """Get all WhatsApp chats involving the contact.

            Args:
                jid: The contact's JID to search for
                limit: Maximum number of chats to return (default 20)
                page: Page number for pagination (default 0)
            """
            chats = whatsapp_tools.get_contact_chats(self.db, jid, limit, page)
            return chats

        @self.mcp.tool()
        def get_last_interaction(jid: str) -> str:
            """Get most recent WhatsApp message involving the contact.

            Args:
                jid: The JID of the contact to search for
            """
            message = whatsapp_tools.get_last_interaction(jid)
            return message

        @self.mcp.tool()
        def get_message_context(
            message_id: str, before: int = 5, after: int = 5
        ) -> Dict[str, Any]:
            """Get context around a specific WhatsApp message.

            Args:
                message_id: The ID of the message to get context for
                before: Number of messages to include before the target message (default 5)
                after: Number of messages to include after the target message (default 5)
            """
            context = whatsapp_tools.get_message_context(
                self.db, message_id, before, after
            )
            return context

        @self.mcp.tool()
        def send_message(recipient: str, message: str) -> Dict[str, Any]:
            """Send a WhatsApp message to a person or group. For group chats use the JID.

            Args:
                recipient: The recipient - either a phone number with country code but no + or other symbols,
                        or a JID (e.g., "123456789@s.whatsapp.net" or a group JID like "123456789@g.us")
                message: The message text to send

            Returns:
                A dictionary containing success status and a status message
            """
            # Validate input
            if not recipient:
                return {"success": False, "message": "Recipient must be provided"}

            # Call the send_message function with the unified recipient parameter
            success, status_message = whatsapp_tools.send_message(
                self.api_base_url, recipient, message
            )
            return {"success": success, "message": status_message}

        @self.mcp.tool()
        def send_file(recipient: str, media_path: str) -> Dict[str, Any]:
            """Send a file such as a picture, raw audio, video or document via WhatsApp to the specified recipient. For group messages use the JID.

            Args:
                recipient: The recipient - either a phone number with country code but no + or other symbols,
                        or a JID (e.g., "123456789@s.whatsapp.net" or a group JID like "123456789@g.us")
                media_path: The absolute path to the media file to send (image, video, document)

            Returns:
                A dictionary containing success status and a status message
            """
            # Call the send_file function
            success, status_message = whatsapp_tools.send_file(
                self.api_base_url, recipient, media_path
            )
            return {"success": success, "message": status_message}

        @self.mcp.tool()
        def send_audio_message(recipient: str, media_path: str) -> Dict[str, Any]:
            """Send any audio file as a WhatsApp audio message to the specified recipient. For group messages use the JID. If it errors due to ffmpeg not being installed, use send_file instead.

            Args:
                recipient: The recipient - either a phone number with country code but no + or other symbols,
                        or a JID (e.g., "123456789@s.whatsapp.net" or a group JID like "123456789@g.us")
                media_path: The absolute path to the audio file to send (will be converted to Opus .ogg if it's not a .ogg file)

            Returns:
                A dictionary containing success status and a status message
            """
            success, status_message = whatsapp_tools.send_audio_message(
                self.api_base_url, recipient, media_path
            )
            return {"success": success, "message": status_message}

        @self.mcp.tool()
        def download_media(message_id: str, chat_jid: str) -> Dict[str, Any]:
            """Download media from a WhatsApp message and get the local file path.

            Args:
                message_id: The ID of the message containing the media
                chat_jid: The JID of the chat containing the message

            Returns:
                A dictionary containing success status, a status message, and the file path if successful
            """
            file_path = whatsapp_tools.download_media(
                self.api_base_url, message_id, chat_jid
            )

            if file_path:
                return {
                    "success": True,
                    "message": "Media downloaded successfully",
                    "file_path": file_path,
                }
            else:
                return {"success": False, "message": "Failed to download media"}

    def run(self):
        self.mcp.run(transport="stdio")
