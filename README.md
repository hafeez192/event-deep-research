<!-- Improved compatibility of back to top link: See: https://github.com/othneildrew/Best-README-Template/pull/73 -->

<a id="readme-top"></a>

<!-- PROJECT SHIELDS -->

[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![MIT License][license-shield]][license-url]

<!-- PROJECT LOGO -->
<br />
<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
        <li><a href="#configuration">Configuration</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#architecture">Architecture</a></li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>

<!-- ABOUT THE PROJECT -->

## About The Project

Deep Event Research is an intelligent AI agent that automatically discovers, extracts, and compiles biographical events of historical figures. Built with LangGraph, it uses advanced context engineering techniques and a supervisor pattern to orchestrate multiple research agents that work together to create comprehensive life timelines.

[![Agent Graph][graph-screenshot]](https://kronologs.com)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

# What it does?

It looks for information about the historical figure in the web, it extracts the events from the sources and it creates a timeline of the life of the figure.

Start:

```json
{
  "person_to_research": "Henry Miller"
}
```

End:

```json
{
  "events": [
    {
      "name": "Birth in Brooklyn",
      "description": "Lived at 662 Driggs Avenue, Williamsburg, Brooklyn. with his parents",
      "date": {
        "year": 1909,
        "note": "circa"
      },
      "location": {
        "name": "Brooklyn",
        "lat": 40.6526006,
        "lng": -73.9497211
      },
      "id": 1
    },
    {
      "name": "Moved to Bushwick",
      "description": "Moved to Decatur Street, Bushwick, Brooklyn. with his partner Beatrice Sylvas Wickens",
      "date": {
        "year": 1917,
        "note": null
      },
      "location": {
        "name": "Bushwick, Brooklyn",
        "lat": 40.6942696,
        "lng": -73.9187482
      },
      "id": 2
    }
  ]
}
```

### Built With

This project leverages cutting-edge AI and web technologies:

- [![LangGraph][langgraph.com]][langgraph-url] - Multi-agent orchestration and workflow management
- [![LangChain][langchain.com]][langchain-url] - LLM integration and tooling
- [![Firecrawl][firecrawl.com]][firecrawl-url] - Advanced web scraping and content extraction
- [![Tavily][tavily.com]][tavily-url] - Intelligent web search and source discovery
- [![Langfuse][langfuse.com]][langfuse-url] - LLM observability and monitoring
- [![Ollama][ollama.com]][ollama-url] - Local LLM inference

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- GETTING STARTED -->

## Getting Started

### Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.12+**
- **uv** (Python package manager)
- **Ollama** (for local LLM inference)

  ```bash
  # Install Ollama
  curl -fsSL https://ollama.ai/install.sh | sh

  # Pull a model (e.g., I recommend the following models, gpt-oss:20b (for tool selection) and mistral-nemo:latest (for structured output, there is a bug with gpt-oss:20b))
  ollama pull gpt-oss:20b
  ollama pull mistral-nemo:latest
  ```

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/bernatsampera/deep-event-research.git
   cd deep-event-research
   ```

2. **Create virtual environment and install dependencies**

   ```bash
   uv venv && source .venv/bin/activate
   uv sync
   ```

3. **Set up environment variables**
   Create a `.env` file in the root directory:

   ```bash
   # Required API Keys
   FIRECRAWL_API_KEY=your_firecrawl_api_key
   TAVILY_API_KEY=your_tavily_api_key

   # Optional: Langfuse for observability
   LANGFUSE_PUBLIC_KEY=your_langfuse_public_key
   LANGFUSE_SECRET_KEY=your_langfuse_secret_key
   LANGFUSE_HOST=https://cloud.langfuse.com

   # LLM Configuration
   OPENAI_API_KEY=your_openai_api_key  # Optional: for OpenAI models
   GOOGLE_API_KEY=your_google_api_key  # Optional: for Google models
   ```

4. **Start LangGraph Studio**

   ```bash
    uvx --refresh --from "langgraph-cli[inmem]" --with-editable . --python 3.12 langgraph dev --allow-blocking
   ```

5. Langgraph Studio should open at http://localhost:2024 and you should see a graph like this:

   ![Langgraph Studio Graph](images/kronologs-lgstudiograph.webp)

### Configuration

The project uses several configuration files:

- **`langgraph.json`**: Defines the available graphs and their entry points
- **`.env`**: Contains API keys and configuration variables
- **`pyproject.toml`**: Project dependencies and metadata

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- USAGE EXAMPLES -->

## Usage

### Running the Research Agent

1. **Run the Supervisor Graph**

   - Select the `supervisor` graph
   - Input your research query:

   ```json
   {
     "person_to_research": "Albert Einstein"
   }
   ```

2. **Monitor the Research Process**
   The agent will automatically:
   - Search for biographical sources
   - Extract relevant events
   - Categorize events by life periods
   - Merge and deduplicate information
   - Provide a comprehensive timeline

### Example Research Output

```json
{
  "structured_events": [
    {
      "name": "Birth of Albert Einstein",
      "description": "Albert Einstein was born in Ulm, Germany.",
      "date": {
        "year": 1879,
        "note": ""
      },
      "location": "Ulm, Germany",
      "id": "time-1879-03-14T00:00:00Z"
    },
    {
      "name": "Einstein's Family Moves to Munich",
      "description": "Albert Einstein moved with his family to Munich.",
      "date": {
        "year": 1880,
        "note": ""
      },
      "location": "Munich, Germany",
      "id": "time-1880-03-14T00:00:00Z"
    }
  ]
}
```

### Available Graphs

The project includes several specialized graphs:

- **`supervisor`**: Main orchestration graph that coordinates the research process
- **`research_events`**: Handles source discovery and event extraction
- **`merge_events_graph`**: Merges and deduplicates events from multiple sources
- **`url_crawler`**: Extracts content from web pages

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- ARCHITECTURE -->

## Architecture

Deep Event Research uses a sophisticated multi-agent architecture built on LangGraph:

### Core Components

1. **Supervisor Agent**: The main orchestrator that decides research strategy
2. **Research Events Agent**: Handles source discovery and event extraction
3. **URL Crawler Agent**: Extracts content from web pages
4. **Merge Events Agent**: Combines and deduplicates information

### Key Features

- **Context Engineering**: Advanced prompt engineering for accurate event extraction
- **Supervisor Pattern**: Intelligent coordination of multiple specialized agents
- **Event Categorization**: Automatic organization into meaningful life periods
- **Source Quality Assessment**: Intelligent selection of the most reliable sources
- **Observability**: Complete tracking of the research process with Langfuse

<p align="right">(<a href="#readme-top">back to top</a>)</p>

See the [open issues](https://github.com/bernatsampera/deep-event-research/issues) for a full list of proposed features and known issues.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- CONTRIBUTING -->

## Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".
Don't forget to give the project a star! Thanks again!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Development Setup

1. **Install development dependencies**

   ```bash
   uv sync --dev
   ```

2. **Run tests**

   ```bash
   make test
   ```

3. **Start development server**
   ```bash
   make dev
   ```

### Top contributors:

<a href="https://github.com/bernatsampera/deep-event-research/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=bernatsampera/deep-event-research" alt="contrib.rocks image" />
</a>

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- LICENSE -->

## License

Distributed under the MIT License. See `LICENSE.txt` for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- CONTACT -->

## Contact

**Bernat Sampera** - [@bsampera97](https://x.com/bsampera97) - [GitHub](https://github.com/bernatsampera)

Project Link: [https://github.com/bernatsampera/deep-event-research](https://github.com/bernatsampera/deep-event-research)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- ACKNOWLEDGMENTS -->

## Acknowledgments

This project was inspired by and builds upon several amazing open-source projects:

- [Open Deep Research](https://github.com/langchain-ai/open_deep_research) by LangChain - For inspiration on deep research methodologies
- [LangChain](https://github.com/langchain-ai/langchain) - For the foundational LLM framework
- [LangGraph](https://github.com/langchain-ai/langgraph) - For the multi-agent orchestration capabilities

Special thanks to the open-source community for making this project possible!

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->

[contributors-shield]: https://img.shields.io/github/contributors/bernatsampera/deep-event-research.svg?style=for-the-badge
[contributors-url]: https://github.com/bernatsampera/deep-event-research/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/bernatsampera/deep-event-research.svg?style=for-the-badge
[forks-url]: https://github.com/bernatsampera/deep-event-research/network/members
[stars-shield]: https://img.shields.io/github/stars/bernatsampera/deep-event-research.svg?style=for-the-badge
[stars-url]: https://github.com/bernatsampera/deep-event-research/stargazers
[issues-shield]: https://img.shields.io/github/issues/bernatsampera/deep-event-research.svg?style=for-the-badge
[issues-url]: https://github.com/bernatsampera/deep-event-research/issues
[license-shield]: https://img.shields.io/github/license/bernatsampera/deep-event-research.svg?style=for-the-badge
[license-url]: https://github.com/bernatsampera/deep-event-research/blob/master/LICENSE.txt
[langgraph.com]: https://img.shields.io/badge/LangGraph-ffffff?logo=python&logoColor=blue
[langgraph-url]: https://github.com/langchain-ai/langgraph
[langchain.com]: https://img.shields.io/badge/LangChain-ffffff?logo=python&logoColor=blue
[langchain-url]: https://www.langchain.com/
[firecrawl.com]: https://img.shields.io/badge/Firecrawl-ffffff?logo=firebase&logoColor=orange
[firecrawl-url]: https://firecrawl.dev/
[tavily.com]: https://img.shields.io/badge/Tavily-ffffff?logo=algolia&logoColor=green
[tavily-url]: https://tavily.com/
[langfuse.com]: https://img.shields.io/badge/Langfuse-ffffff?logo=chartdotjs&logoColor=purple
[langfuse-url]: https://langfuse.com/
[ollama.com]: https://img.shields.io/badge/Ollama-ffffff?logo=robotframework&logoColor=blue
[ollama-url]: https://ollama.ai/
[graph-screenshot]: images/kronologs-graph.webp
