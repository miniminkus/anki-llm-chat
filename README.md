# Card Assistant — LLM Chat for Anki

**Add-on Code:** `940044876` — [ankiweb.net/shared/info/940044876](https://ankiweb.net/shared/info/940044876)

A side-panel chat assistant that lets you ask questions about your flashcards while reviewing. Connects to **OpenRouter** (hundreds of models), a local **Ollama** instance, or **Google Gemini** (free-tier models available).

## Features

- Streams responses in a dockable side panel during review
- Works with any note type — fields are extracted automatically
- Supports OpenRouter, Ollama, and Gemini as providers, each remembering its own model
- Markdown rendering (code blocks, lists, headings, etc.)
- Customisable system prompt, temperature, max tokens, font size, and panel width
- Context-aware: sends the current card's fields to the LLM automatically
- Collapse/expand the panel to stay out of your way

## Installation

1. Download or clone this repository
2. Copy the folder into your Anki add-ons directory:
   - **macOS:** `~/Library/Application Support/Anki2/addons21/`
   - **Windows:** `%APPDATA%\Anki2\addons21\`
   - **Linux:** `~/.local/share/Anki2/addons21/`
3. Rename the folder to `card_assistant` (must match the package name)
4. Restart Anki

## Configuration

Open **Tools > Add-ons > Card Assistant > Config** or click the gear icon in the panel.

### OpenRouter
1. Get an API key from [openrouter.ai](https://openrouter.ai/)
2. Select "OpenRouter" as provider
3. Paste your API key
4. Click "Refresh" to load available models, or type a model ID directly
5. Click "Test Connection" to verify everything works

### Ollama
1. Install [Ollama](https://ollama.ai/) and pull a model (e.g. `ollama pull llama3`)
2. Select "Ollama" as provider
3. Set the URL (default: `http://localhost:11434`)
4. Click "Refresh" to see your local models
5. Click "Test Connection" to verify

### Gemini
1. Get a free API key from [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Select "Gemini" as provider
3. Paste your API key
4. Click "Refresh" to load available models, or type a model ID directly
5. Click "Test Connection" to verify

## Usage

1. Start reviewing cards — the panel appears automatically on the right
2. Type a question about the current card and press Enter
3. The assistant streams its response with the card's content as context
4. Click the stop button to cancel a response mid-stream
5. The chat resets when you move to the next card

## Requirements

- Anki 2.1.50+
- Internet connection (for OpenRouter/Gemini) or a running Ollama server

## License

[MIT](LICENSE)
