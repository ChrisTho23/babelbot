# BabelBot
Simple AI agent that connects and translates text and audio into different languages in WhatsApp. Built via Luke Harries's [WhatsApp MCP server](https://github.com/lharries/whatsapp-mcp).

You can find BabelBot's WhatsApp number [here](https://hey-eve-website.vercel.app/)!

## Tutorial

Find a video where I explain the idea behind the project, its architecture, and show a few examplary applications [here](https://drive.google.com/drive/u/1/folders/183KZosY9G-Xq4pR2IHoohddU2Pbo4it_?dmr=1&ec=wgc-drive-globalnav-goto)!

## System Architecture

![Screenshot 2025-04-06 at 3 58 42 PM](https://github.com/user-attachments/assets/89737a79-c90c-43ba-9c08-05a2d8ee8b46)


## Setup & Installation

1. **Install Dependencies**
   ```bash
   # Install dependencies using uv (recommended)
   uv pip install -r pyproject.toml

   # Alternative: using pip
   pip install anthropic>=0.49.0 fastapi>=0.115.12 fire>=0.7.0 httpx>=0.28.1 mcp[cli]>=1.6.0 openai>=1.70.0 python-dotenv>=1.1.0 requests>=2.32.3
   ```

2. **Configure Environment Variables**
   Create a `.env` file in the root directory with the following content:
   ```env
   # Anthropic API Key
   ANTHROPIC_API_KEY="your-anthropic-key"

   # OpenAI API Key
   OPENAI_API_KEY="your-openai-key"

   # Webhook URL (default for local development)
   WEBHOOK_URL="http://localhost:8000/webhook"
   ```

3. **Start the WhatsApp Bridge**
   ```bash
   # Navigate to the bridge directory
   cd babelbot/whatsapp-mcp/whatsapp-bridge

   # Run the bridge
   go run main.go
   ```
   - On first run, you'll see a QR code in the terminal
   - Scan this with WhatsApp mobile app: Settings -> Linked Devices -> Link a Device
   - The bridge will start on port 8080

4. **Start the FastAPI Application**
   ```bash
   # From the root directory
   python -m babelbot.app.main
   ```
   - The API server will start on http://localhost:8000
   - API documentation available at http://localhost:8000/docs

## Note
- The bridge needs to be running before starting the FastAPI application
- Make sure to keep your API keys secure and never commit them to version control
- The WhatsApp session will persist in the `store` directory created by the bridge
