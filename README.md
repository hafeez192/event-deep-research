# 🕵️ Event Deep Research

**Problem**:
In many old books there are small chronologies of the life events of authors and other relevant historical figures. But each of these
chronologies are in specific books, they are not easy to find.

**Solution**:
An AI agent that automatically discovers sources, extract events, and compile structured JSON timelines.

**Key Highlights**:
Multi-agent system with intelligent crawling, real-time visualization, and support for OpenAI, Anthropic, Google, or Ollama models.

<img src="media/event-deep-research.webp" alt="Event Deep Research" width="600"/>

<img src="media/kronologs-graph.webp" alt="Agent Graph" />

<video src="media/eventdeepresearch-demo.mp4" alt="Event Deep Research Demo" width="600"> </video>

## ✨ Features

- **🔍 Automated Biographical Research** - Input any historical figure and get comprehensive event timelines
- **🕷️ Intelligent Web Crawling** - Automatically discovers and extracts information from multiple sources
- **📊 Structured Event Extraction** - Converts unstructured web content into clean, chronological JSON timelines
- **🤖 Multi-Agent Coordination** - Specialized agents work together to research, crawl, and merge data
- **🎯 Real-Time Visualization** - Watch the AI agents work through LangGraph Studio's interactive interface
- **🔧 Flexible LLM Support** - Works with OpenAI, Anthropic, Google, or local Ollama models

## 🎯 What You'll Learn

This project demonstrates advanced AI agent patterns and techniques:

- **Multi-Agent Orchestration** with LangGraph's supervisor pattern
- **Context Engineering** for accurate information extraction
- **Web Scraping & Search Integration** with real-time data sources
- **Structured Output Generation** from unstructured web content
- **Error Handling & State Management** in complex workflows
- **Testing Strategies** for LLM-powered applications

## ⚡ Quick Test (5 minutes)

```bash
# 1. Clone and setup
git clone https://github.com/bernatsampera/deep-event-research.git
cd deep-event-research
uv venv && source .venv/bin/activate
uv sync

# 2. Add your API keys to .env
cp .env.example .env
# Edit .env with your FIRECRAWL_API_KEY and TAVILY_API_KEY

# 3. Run tests (no API calls needed)
make test

# 4. Start the visual agent studio
make dev
# Open http://localhost:2024 and try researching "Albert Einstein"
```

## 🔄 How It Works

**Input:**

```json
{
  "person_to_research": "Albert Einstein"
}
```

**Output:**

```json
{
  "structured_events": [
    {
      "name": "Birth in Ulm",
      "description": "Albert Einstein was born in Ulm, Germany to Hermann and Pauline Einstein",
      "date": {"year": 1879, "note": "March 14"},
      "location": "Ulm, German Empire",
      "id": "time-1879-03-14T00:00:00Z"
    },
    {
      "name": "Zurich Polytechnic",
      "description": "Entered the Swiss Federal Polytechnic School in Zurich to study physics and mathematics",
      "date": {"year": 1896, "note": ""},
      "location": "Zurich, Switzerland",
      "id": "time-1896-01-01T00:00:00Z"
    },
    {
      "name": "Miracle Year Papers",
      "description": "Published four groundbreaking papers on photoelectric effect, Brownian motion, special relativity, and mass-energy equivalence",
      "date": {"year": 1905, "note": ""},
      "location": "Bern, Switzerland",
      "id": "time-1905-01-01T00:00:00Z"
    },
    {
      "name": "Nobel Prize in Physics",
      "description": "Awarded Nobel Prize for his discovery of the law of the photoelectric effect",
      "date": {"year": 1921, "note": ""},
      "location": "Stockholm, Sweden",
      "id": "time-1921-01-01T00:00:00Z"
    },
    {
      "name": "Death in Princeton",
      "description": "Albert Einstein died at Princeton Hospital after refusing surgery for an abdominal aortic aneurysm",
      "date": {"year": 1955, "note": "April 18"},
      "location": "Princeton, New Jersey, USA",
      "id": "time-1955-04-18T00:00:00Z"
    }
  ]
}
```

## 🛠️ Tech Stack

- **[LangGraph](https://github.com/langchain-ai/langgraph)** - Multi-agent orchestration
- **[LangChain](https://github.com/langchain-ai/langchain)** - LLM integration
- **[Firecrawl](https://firecrawl.dev/)** - Web scraping
- **[Tavily](https://tavily.com/)** - Intelligent search
- **Python 3.12+** with async/await patterns

## 🚀 Installation

### Prerequisites

- **Python 3.12+**
- **uv** (Python package manager)

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/bernatsampera/deep-event-research.git
cd deep-event-research

# 2. Create virtual environment and install dependencies
uv venv && source .venv/bin/activate
uv sync

# 3. Set up environment variables
cp .env.example .env
# Edit .env with your API keys:
# - FIRECRAWL_API_KEY (required for production, optional for local testing)
# - TAVILY_API_KEY (required)
# - OPENAI_API_KEY, ANTHROPIC_API_KEY, or GOOGLE_API_KEY (optional, for LLM)

# 4. Start the development server
make dev
# Open http://localhost:2024 to access LangGraph Studio
```

### Model Configuration

The project supports multiple LLM providers with simplified configuration. Set a single `LLM_MODEL` environment variable in your `.env` file:

**Supported Model Formats:**

- `openai:gpt-4o` - OpenAI GPT models
- `anthropic:claude-3-5-sonnet-20241022` - Anthropic Claude models
- `google:gemini-1.5-pro` - Google Gemini models
- `ollama:mistral-nemo:latest` - Local Ollama models

**Example `.env` Configuration:**

```bash
# Use OpenAI (single model works for both structured output and tools)
LLM_MODEL="openai:gpt-4o"
OPENAI_API_KEY="your-openai-api-key"

# Use Google (single model works for both structured output and tools)
LLM_MODEL="google:gemini-1.5-pro"
GOOGLE_API_KEY="your-google-api-key"

# Use Anthropic (single model works for both structured output and tools)
LLM_MODEL="anthropic:claude-3-5-sonnet-20241022"
ANTHROPIC_API_KEY="your-anthropic-api-key"

# Use Ollama (automatically handles dual models due to gpt-oss structured output bug)
LLM_MODEL="ollama:mistral-nemo:latest"
# Optional: Override the automatic dual model selection
# STRUCTURED_LLM_MODEL="ollama:mistral-nemo:latest"
# TOOLS_LLM_MODEL="ollama:gpt-oss:20b"
```

**Default values** (if not set in environment):

- `LLM_MODEL="ollama:mistral-nemo:latest"`
- For Ollama: automatically uses `mistral-nemo` for structured output and `gpt-oss` for tools

### API Keys Setup

You'll need these free API keys:

- **[Firecrawl](https://firecrawl.dev/)** - Web scraping (get free API key, optional for local testing)
- **[Tavily](https://tavily.com/)** - Web search (get free API key)
- **LLM Provider** (choose one or more):
  - **[OpenAI](https://platform.openai.com/)** - GPT models
  - **[Anthropic](https://console.anthropic.com/)** - Claude models
  - **[Google AI](https://aistudio.google.com/)** - Gemini models
  - **Ollama** - Local models (no API key needed)

## 🧪 Testing

```bash
# Run specific test
uv run pytest src/test/test_research_events.py::test_research_events_with_mocked_llm -v

# Run tests with real LLM calls (requires API keys)
uv run pytest -v -m llm
```

## 🎮 Usage

### Via LangGraph Studio (Recommended)

1. Start the development server: `make dev`
2. Open http://localhost:2024
3. Select the `supervisor` graph
4. Input your research query:
   ```json
   {
     "person_to_research": "Leonardo da Vinci"
   }
   ```
5. Watch the agents work in real-time!

### What the Agents Do

1. **🔍 Research Agent** - Finds relevant biographical sources
2. **🕷️ URL Crawler** - Extracts content from web pages
3. **📊 Merge Agent** - Combines and deduplicates events
4. **🎯 Supervisor** - Coordinates the entire workflow

### Example Output

```json
{
  "structured_events": [
    {
      "name": "Birth in Vinci",
      "description": "Leonardo da Vinci was born in Vinci, Italy",
      "date": {"year": 1452, "note": ""},
      "location": "Vinci, Italy",
      "id": "time-1452-04-15T00:00:00Z"
    }
  ]
}
```

![Langgraph Studio Graph](media/kronologs-lgstudiograph.webp)

## 📁 Project Structure

```
src/
├── core/                 # Shared utilities (error handling)
├── services/             # Business logic services
├── research_events/      # Event extraction & merging
├── url_crawler/          # Web scraping agents
└── state.py             # TypedDict state definitions
```

See the [open issues](https://github.com/bernatsampera/deep-event-research/issues) for a full list of proposed features and known issues.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## 🤝 Contributing

We welcome contributions! This is a great project to learn:

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/amazing-feature`
3. **Commit** your changes: `git commit -m 'Add amazing feature'`
4. **Push** to the branch: `git push origin feature/amazing-feature`
5. **Open** a Pull Request

### Development Commands

```bash
# Start dev server
make dev
```

## 📄 License

Distributed under the MIT License. See `LICENSE.txt` for details.

## 🙏 Acknowledgments

- **[LangChain](https://github.com/langchain-ai/langchain)** - Foundational LLM framework
- **[LangGraph](https://github.com/langchain-ai/langgraph)** - Multi-agent orchestration
- **[Open Deep Research](https://github.com/langchain-ai/open_deep_research)** - Research methodology inspiration

---

<div align="center">

**⭐ Star this repo if it helped you learn about AI agents!**

Made with ❤️ by [Bernat Sampera](https://github.com/bernatsampera)

</div>
