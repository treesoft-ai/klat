# 🌿 Klat — "The greenest, yet powerful SWE Agent"

Klat is simply the only SWE Agent you'll ever need. It's easy to get started, and as easy to master. Made by TreeSoft, for **everyone** (developers or future ones).

## Setup

Requires Python 3.10+.

### Option 1: Using `uv` (Fastest)

If you have [uv](https://github.com/astral-sh/uv) installed, run:
```bash
uv run main.py
```
It will bootstrap the virtual environment and fetch dependencies automatically.

### Option 2: Standard python

```bash
# Create and activate environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies and run
pip install -r requirements.txt
python main.py
```

## Configuration

On first run, an interactive wizard prompts you for API keys. Configuration is stored in your home directory at `~/.klat/settings/config.json`.

### Supported providers

Provide these keys during first-time setup or configure them in `config.json`:

| Provider | Config key | Default model |
| :--- | :--- | :--- |
| **Vertex AI** | `google_cloud_project` / `google_cloud_location` | `gemini-1.5-pro-002` |
| **AI Studio** | `gemini_api_key` | `gemini-2.5-pro` |
| **Anthropic** | `anthropic_api_key` | `claude-3-5-sonnet-latest` |
| **OpenAI** | `openai_api_key` | `gpt-4o` |
| **OpenRouter** | `openrouter_api_key` | `anthropic/claude-3.5-sonnet` |
| **NVIDIA NIM** | `nvidia_api_key` | `meta/llama-3.1-70b-instruct` |

## Slash commands

You can run commands during a chat session to configure settings or manage extensions:

* `/provider` — List active and available providers
* `/provider <name>` — Switch to a different provider
* `/model` — Show the active model
* `/model <name>` — Switch to a specific model
* `/extension list` — Show installed extensions
* `/extension export <folder>` — Bundle a directory into a `.ke` file
* `/extension import <path>` — Install and load a `.ke` extension
* `/extension enable <name>` — Enable an extension
* `/extension disable <name>` — Disable an extension
* `/extension remove <name>` — Uninstall an extension
* `/reset` — Clear conversation history
* `q` / `exit` / `quit` — Exit the terminal application

## Extensions

Extensions are self-contained plugins that dynamically add custom system rules, prompts, and tools to Klat. They are packaged as `.ke` files, which are imported and hot-loaded instantly without restarting the application.

### Architecture

An extension consists of a single directory containing exactly two files:

* **`manifest.json`**: Defines the metadata (name, version, description) and specifies JSON schemas for any custom functions (tools) you want the LLM to call.
* **`main.py`**: Contains the Python logic executing your custom functions. It integrates with Klat's core through an automatically injected virtual `klat` SDK.

### The virtual SDK

When Klat loads an extension, it provides a virtual `klat` module. Through this SDK, extensions can:

* Register custom rules to the system prompt (`klat.system_prompt.add_rule`)
* Stream text outputs directly as the agent (`klat.ai.say`)
* Output background system diagnostic logs (`klat.log`)
* Apply default green/dim terminal colors (`klat.ui`)

### Lifecycle workflow

1. **Development**: Create a folder with your `manifest.json` schemas and `main.py` entrypoint handlers.
2. **Packaging**: Run `/extension export /path/to/folder` inside Klat to validate and bundle the files into a single `.ke` archive.
3. **Activation**: Load the tool using `/extension import /path/to/file.ke`. Once approved via the safety prompt, all new tools, features and rules become active instantly.

## Roadmap

* **Node.js Transition**: Porting the core architecture to Node.js to align with industry standards for modern, asynchronous SWE agents and tap into a broader ecosystem of developer tools.
* **VS Code Integration**: Developing a native VS Code extension to bring Klat's full agentic capabilities, interactive tools, and hot-loading system directly into the editor where you write your code.