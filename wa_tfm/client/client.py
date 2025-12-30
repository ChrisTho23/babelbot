import asyncio
import json
from contextlib import AsyncExitStack
from typing import ClassVar, Optional

from anthropic import Anthropic
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import AsyncOpenAI

from ..app.routers.webhook.models import WhatsAppMessage

load_dotenv()

class MCPClient:
    _instance: ClassVar[Optional['MCPClient']] = None
    _initialized: bool = False
    _initialization_lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.session: Optional[ClientSession] = None
            self.exit_stack = AsyncExitStack()
            self.anthropic = Anthropic()
            self.openai = AsyncOpenAI()
            self.openai
            self._initialized = True

            self.system_prompt = """You are a WhatsApp Helper Agent designed to assist users in translating and rewriting their messages for WhatsApp conversations in a culturally appropriate, fluent, and context-sensitive way. Users will send you text or voice messages in their native language, expressing what they want to communicate and to whom. Your task is to deeply understand their intent, infer the proper tone based on the relationship and context (e.g., casual friend, work colleague, boss), and craft a native-sounding WhatsApp message in the target language.
            If the user requests your help to formulate a message for them to send to another person, comply and draft a WhatsApp message 
            according to the user's request. Make sure the message is authentic and follows the user's instructions. Return only the 
            formulated message and nothing else. If the user's request is not related to formulating a message, respond with 'I am only here 
            to help you formulate WhatsApp messages. For other inquiries, please turn towards other services.'

            TASK FLOW:
            1.⁠ ⁠*Understand the Message & Intent*: Analyze what the user wants to say, who they are speaking to, and why.
            2.⁠ ⁠*Infer the Appropriate Tone*: Decide whether the message should sound casual, professional, apologetic, friendly, respectful, etc.
            3.⁠ ⁠*Translate & Adapt*: Recreate the message in the target language with appropriate tone and WhatsApp-friendly formatting (e.g., emojis only if appropriate, short paragraphs, contractions, etc.).
            4.⁠ ⁠*Output Only the Final Message*: Return only the rewritten message that the user can copy-paste directly into WhatsApp. Do not include explanations or translations unless explicitly requested.

            STYLE GUIDELINES:
            •⁠  ⁠Messages must be native-sounding and context-aware.
            •⁠  ⁠Default to concise and clear communication suitable for WhatsApp.
            •⁠  ⁠Assume a texting format: contractions and informal punctuation are okay when contextually appropriate.
            •⁠  ⁠Always match the cultural tone and professionalism level expected in the recipient's language and relationship.

            LANGUAGE CAPABILITIES:
            You can understand and respond in multiple languages (including Spanish, Portuguese, French, etc.) and rewrite them into native-quality English, or vice versa, depending on user instruction or context clues.

            IMPORTANT - RECIPIENT HANDLING:
            •⁠  ⁠When responding to the user, ALWAYS use the 'chat_jid' field as the recipient (e.g., "1234567890@lid" or "1234567890@s.whatsapp.net").
            •⁠  ⁠Do NOT strip the @lid or @s.whatsapp.net suffix - use the full chat_jid exactly as provided.
            •⁠  ⁠The chat_jid is the correct identifier for sending messages back to the user.

            VOICE MESSAGE GUIDELINES:
            •⁠  ⁠By default, ALWAYS use 'send_message' to send TEXT responses.
            •⁠  ⁠ONLY use 'send_voice_message' when the user EXPLICITLY requests a voice message, audio response, or says something like:
                - "send as voice", "als Sprachnachricht", "voice message", "Sprachnachricht", "audio", "speak this", "say this out loud"
                - "antworte mir mit einer Sprachnachricht", "schick mir das als Audio"
            •⁠  ⁠When using send_voice_message, you can choose a voice: alloy, echo, fable, onyx, nova, or shimmer.
            •⁠  ⁠For voice messages, keep the text natural and conversational - it will be spoken aloud.

            Here are three examples:

            Example 1 (Turkish to German):  
            User: {"sender": "1234567890", "chat_jid": "1234567890@s.whatsapp.net", "content": "Abla, öğretmenime yazmak istiyorum. Derse geç kaldım ama yoldayım."}  
            send_message: {"recipient": "1234567890@s.whatsapp.net", "message": "Hallo Frau Schneider, ich wollte nur kurz Bescheid geben, dass ich ein paar Minuten später komme – bin schon unterwegs."}

            Example 2 (Arabic to German with LID):  
            User: {"sender": "9876543210", "chat_jid": "9876543210@lid", "content": "بدي أكتب لبنت خالتي شكراً إنها ساعدتني مع الشغل."}
            send_message: {"recipient": "9876543210@lid", "message": "Hey, danke dir nochmal für deine Hilfe mit der Arbeit gestern – war echt mega lieb von dir!"}

            Example 3 (German to English):  
            User: {"sender": "5555555555", "chat_jid": "5555555555@s.whatsapp.net", "content": "Ich will meinem Chef schreiben, dass ich Homeoffice mache, weil der Handwerker kommt."}
            send_message: {"recipient": "5555555555@s.whatsapp.net", "message": "Morning! Just a heads-up – I'll be working from home today, got someone coming over to fix something."}

            Example 4 (Voice message request):  
            User: {"sender": "1234567890", "chat_jid": "1234567890@lid", "content": "Schreib meinem Chef dass ich krank bin, schick es als Sprachnachricht"}
            send_voice_message: {"recipient": "1234567890@lid", "text": "Hey Chef, wollte kurz Bescheid sagen dass ich heute leider krank bin und nicht kommen kann. Melde mich sobald es mir besser geht.", "voice": "onyx"}

            IN ANY CASE USE THE 'send_message' OR 'send_voice_message' TOOL TO COMMUNICATE YOUR ANSWER TO THE USER, OTHERWISE HE WILL NOT SEE YOUR RESPONSE.
            Do not include any meta-commentary about using tools or sending messages - just provide the response content.
            """

    @classmethod
    async def get_instance(cls) -> 'MCPClient':
        if cls._instance is None:
            async with cls._initialization_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP server

        Args:
            server_script_path: Path to the server script (.py or .js)
        """
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")

        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=None
        )

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()

        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        print("\nConnected to server with tools:", [tool.name for tool in tools])

    async def transcribe_audio(self, audio_path: str) -> str:
        """Transcribe audio file using OpenAI's Whisper API"""
        try:
            with open(audio_path, "rb") as audio_file:
                transcript = await self.openai.audio.transcriptions.create(
                    model="gpt-4o-transcribe",
                    file=audio_file,
                    response_format="text"
                )
                return transcript
        except Exception as e:
            print(f"Transcription error: {str(e)}")
            raise

    async def process_query(self, message: WhatsAppMessage) -> str:
        """Process a query using Claude and available tools"""
        if message.media_type:
            if message.media_type == "audio":
                try:
                    download_result = await self.session.call_tool("download_media", {
                        "message_id": message.message_id,
                        "chat_jid": message.chat_jid
                    })
                    
                    if download_result and download_result.content:
                        # Parse the JSON string from the text content
                        result_json = json.loads(download_result.content[0].text)
                        print("Parsed result:", result_json)
                        
                        if result_json.get("success"):
                            audio_path = result_json.get("file_path")
                            print(f"Audio downloaded to: {audio_path}")
                            
                            # Transcribe the audio
                            transcript = await self.transcribe_audio(audio_path)
                            print(f"Transcription: {transcript}")
                        else:
                            print("Download failed:", result_json.get("message"))
                            transcript = "[Failed to download audio message]"
                    else:
                        print("No valid download result")
                        transcript = "[Failed to download audio message]"
                except Exception as e:
                    print(f"Error processing audio: {str(e)}")
                    transcript = "[Failed to download audio message]" 
                message.content = transcript
            else:
                message.content = f"User provided not supported media type {message.media_type}!"

        query = {
            "sender": message.sender,
            "chat_jid": message.chat_jid,
            "content": message.content
        }

        messages = [
            {
                "role": "user",
                "content": json.dumps(query)
            }
        ]

        response = await self.session.list_tools()
        available_tools = [{
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema
        } for tool in response.tools]

        # Initial Claude API call
        response = self.anthropic.messages.create(
            model="claude-sonnet-4-20250514",
            system=self.system_prompt,
            max_tokens=1000,
            messages=messages,
            tools=available_tools
        )

        # Process response and handle tool calls
        final_text = []

        assistant_message_content = []
        for content in response.content:
            if content.type == 'text':
                final_text.append(content.text)
                assistant_message_content.append(content)
            elif content.type == 'tool_use':
                tool_name = content.name
                tool_args = content.input

                # Execute tool call
                result = await self.session.call_tool(tool_name, tool_args)
                final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")

                assistant_message_content.append(content)
                messages.append({
                    "role": "assistant",
                    "content": assistant_message_content
                })
                messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": content.id,
                            "content": result.content
                        }
                    ]
                })

                # Get next response from Claude
                response = self.anthropic.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1000,
                    messages=messages,
                    tools=available_tools
                )

                final_text.append(response.content[0].text)

        return "\n".join(final_text)
    
    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")

        while True:
            try:
                query = input("\nQuery: ").strip()

                if query.lower() == 'quit':
                    break

                response = await self.process_query(query)
                print("\n" + response)

            except Exception as e:
                print(f"\nError: {str(e)}")

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()