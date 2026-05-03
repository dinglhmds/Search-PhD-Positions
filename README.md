# Search-PhD-Positions

This is a Python application for an automated PhD application system, specifically designed to help PhD applicants find and contact potential supervisors. The system leverages AI technologies to automatically search for and parse faculty information from university websites, and generates personalized outreach emails.

## Features

- **Automated Supervisor Search**: Uses an AI-powered search engine to automatically locate university faculty webpages  
- **Information Extraction**: Extracts supervisor names, titles, research areas, email addresses, and homepage links from web pages  
- **University Standardization**: Standardizes university names and domains using YAML configuration or AI models  
- **Personalized Email Generation**: Generates tailored outreach emails based on the applicant's background  
- **Web Interface**: Provides an intuitive web interface for browsing and managing target supervisors  
- **User Profile Management**: Saves and manages applicant profile information  

## Technical Architecture

The system adopts a modular agent-based architecture:  
- **SearchAgent**: Performs Google searches using SerpApi  
- **PlannerAgent**: Standardizes university names  
- **CrawlerAgent**: Asynchronously crawls web pages  
- **ParserAgent**: Parses content using AI  
- **EmailAgent**: Generates intelligent emails  
- **FastAPI**: Serves as the web framework and API interface  

## Environment Setup

### 1. Clone the repository

```bash
git clone <repository-url>
cd PhD-App
```

### 2. Install dependencies (using uv)

This project uses [uv](https://docs.astral.sh/uv/) to manage the virtual environment and dependencies.

```bash
# Install project dependencies (automatically creates .venv)
uv sync

# Or sync production dependencies only
uv sync --no-dev
```

If you haven't installed uv yet, please refer to the [official documentation](https://docs.astral.sh/uv/getting-started/installation/).

### 3. Configure environment variables

Create a `.env` file and add the following configurations:

```env
SEARCH_API_KEY=your_serpapi_key_here
LLM_API_KEY=your_siliconflow_api_key_here
RUNS_DIR=./runs
```

### 4. API service setup

- **SerpApi**: Obtain a Google Search API key for searching faculty pages  
- **SiliconFlow**: Obtain an AI model API key for parsing and content generation  

### 5. Launch the application

```bash
uv run python main.py
```

The application will run at `http://127.0.0.1:8000`

## Usage Instructions

1. Enter a university name on the homepage (e.g., "Stanford", "MIT", "UCB", etc.)  
2. The system will automatically search, crawl, parse, and display faculty information from that university  
3. Browse the faculty list and click to view details or bookmark profiles  
4. Fill in your personal information on the "Profile" page  
5. Click the "Write Email" button next to a faculty member's information to generate a personalized email  

## Project Structure

```
PhD-App/
├── main.py              # Main application file
├── pyproject.toml       # Project config and dependencies (managed by uv)
├── .python-version      # Python version lock
├── .env                 # Environment variable configuration
├── configs/
│   └── universities.yaml # University name mapping configuration
├── runs/               # Directory for storing run results
├── src/
│   └── agents/         # AI agent modules
│       ├── search_agent.py    # Search agent
│       ├── planner_agent.py   # Planner agent
│       ├── crawler_agent.py   # Crawler agent
│       ├── parser_agent.py    # Parser agent
│       └── email_agent.py     # Email agent
├── static/             # Static assets
└── .venv/              # Virtual environment (auto-created by uv)
```

## Notes

- A valid SerpApi key is required for Google searches  
- A valid SiliconFlow API key is required for AI services  
- Comply with the target websites' robots.txt and terms of use  
- Search and crawling operations may take several minutes, depending on website response times
