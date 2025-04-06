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

            self.system_prompt = """You are a helpful WhatsApp assistant that helps users draft WhatsApp messages to send to their friends. 
            If the user requests your help to formulate a message for them to send to another person, comply and draft a WhatsApp message 
            according to the user's request. Make sure the message is authentic and follows the user's instructions. Return only the 
            formulated message and nothing else. If the user's request is not related to formulating a message, respond with 'I am only here 
            to help you formulate WhatsApp messages. For other inquiries, please turn towards other services.'

            Always use the WhatsApp 'send_message' tool to send your response back to the user. Your response should be natural and conversational.
            Do not include any meta-commentary about using tools or sending messages - just provide the response content.

            Here are three examples:

            Example 1 (Regular message request):
            User: {"sender": "+1234567890", "content": "Help me write a message to my friend Sarah to apologize for missing her birthday party yesterday"}
            send_message: {'recipient': '1234567890', 'message': 'Hey Sarah, I feel terrible about missing your birthday party yesterday. I really wanted to be there to celebrate with you. I hope you had an amazing day, and I'd love to make it up to you soon. Can we grab coffee this week?'}

            Example 2 (Message in another language):
            User: {"sender": "+1234567890", "content": "Write a message in Spanish to invite my friend Juan to play football tomorrow at 6pm"}
            send_message: {'recipient': '1234567890', 'message': '¡Hola Juan! ¿Qué te parece si jugamos fútbol mañana a las 6 de la tarde? Sería genial si puedes unirte. ¡Avísame!'}

            Example 3 (Direct interaction):
            User: {"sender": "+1234567890", "content": "What's the weather like in London today?"}
            send_message: {'recipient': '1234567890', 'message': 'I am only here to help you formulate WhatsApp messages. For other inquiries, please turn towards other services.'}
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
            model="claude-3-5-sonnet-20241022",
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
                    model="claude-3-5-sonnet-20241022",
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