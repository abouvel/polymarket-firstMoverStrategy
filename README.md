AI-Powered Polymarket Trading Bot
=================================

An AI trading system that monitors Twitter for market-relevant content, processes it through an AI pipeline, and executes automated trades on Polymarket based on LLM analysis. I chose polymarket over the stock market due to a lack of traditional players, and subsequently higher inefficiencies.

<img width="538" height="408" alt="image" src="https://github.com/user-attachments/assets/2bd97696-29c3-49e7-99ee-8ee74eafd5ed" />
 *Real-time dashboard showing live tweet monitoring and trading activity*

What This Project Does
----------------------

This system combines social media monitoring, AI analysis, and automated trading:

1.  **Twitter Monitoring**: Scrapes Twitter content from specified accounts using browser automation
2.  **AI Content Analysis**: Processes tweets through a LangGraph pipeline with web search and market relevance analysis
3.  **Vector Search Matching**: Uses ChromaDB to find relevant prediction markets based on tweet content similarity
4.  **Automated Trading**: Makes trading decisions using LLaMA 3.2 and executes trades on Polymarket
5.  **Real-time Price Tracking**: Maintains current bid/ask prices via WebSocket connections

System Architecture
-------------------

### Data Flow

```
Twitter → driver.py → FastAPI Webhook → ChromaDB Storage
                           ↓
ChromaDB → LangGraph Pipeline → Market Analysis → Trade Execution
             ↓                        ↓
    Web Search Enhancement    PostgreSQL Logging
```

### Core Components

1.  **`driver.py`**: Twitter scraper using Chrome automation
2.  **`twitterWebhook.py`**: FastAPI server handling tweet ingestion
3.  **`langgraphPipe.py`**: AI analysis pipeline with structured outputs
4.  **`websocketPoly.py`**: Real-time market price monitoring

### AI Pipeline Steps

1.  **Content Enrichment**: Web search via Tavily API
2.  **Vector Similarity**: ChromaDB semantic matching
3.  **Market Analysis**: LLM-based relevance scoring
4.  **Trade Decision**: Structured output with reasoning
5.  **Significance Check**: Evaluates potential for >5% price movement
6.  **Execution Logging**: PostgreSQL trade records

Tech Stack
----------

### AI & Machine Learning

-   **LangGraph**: Multi-step AI workflow orchestration
-   **LangChain**: LLM framework and integrations
-   **Ollama**: Local LLM inference (LLaMA 3.2)
-   **HuggingFace Transformers**: Text embeddings (all-MiniLM-L6-v2)
-   **ChromaDB**: Vector database for semantic search

### Backend & APIs

-   **FastAPI**: High-performance webhook server
-   **PostgreSQL**: Structured data storage (markets, trades)
-   **Tavily**: Web search enrichment API
-   **Polymarket API**: Trading execution and market data

### Automation & Frontend

-   **nodriver**: Chrome browser automation for Twitter scraping
-   **WebSockets**: Real-time Polymarket price feeds
-   **Next.js**: React-based dashboard framework
-   **TypeScript**: Type-safe frontend development
-   **Docker Compose**: Multi-service orchestration

Frontend Dashboard
------------------

Real-time Next.js dashboard with comprehensive monitoring capabilities:

-   **Live Tweet Monitoring**: Real-time display of incoming tweets
-   **Trading Activity Tracking**: Visualization of executed and skipped trades
-   **Connection Status**: Live backend connectivity indicator
-   **Real-time Updates**: Server-Sent Events (SSE) for instant data streaming

**Access Points**:

-   Dashboard: <http://localhost:3000>
-   API: <http://localhost:8000/api/recent>, <http://localhost:8000/events>


Vector Embedding Visualization
------------------

-  **https://www.youtube.com/watch?v=6-y4AuxsqeA**

How to Run
----------

### Environment Setup

1.  Clone and navigate to the project:

bash

```
git clone <repository-url>
cd polyAi/src/backend/expStuff
```

1.  Create environment file:

bash

```
cp .env.example .env
```

1.  Configure your `.env` file:

env

```
# Database Configuration
POSTGRES_USER=your_postgres_user
POSTGRES_PASSWORD=your_secure_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5431
POSTGRES_DB=polymarket_trading

# API Keys
TAVILY_API_KEY=your_tavily_api_key
POLY_KEY=your_polymarket_api_key
POLY_ADDRESS=your_polymarket_wallet_address

# WebSocket Authentication
API_KEY=your_websocket_api_key
API_SECRET=your_websocket_secret
API_PASSPHRASE=your_websocket_passphrase
```

### Start the Application

bash

```
docker-compose up --build
```

This will automatically start all services and launch the dashboard at <http://localhost:3000>.

### Service Management

bash

```
# View service status
docker-compose ps

# Check logs
docker-compose logs -f [service-name]

# Stop services
docker-compose down
```

Configuration Options
---------------------

### Monitored Twitter Users

Edit `MONITORED_USERS` in `driver.py`:

python

```
MONITORED_USERS = ["username1", "username2", "username3"]
```

### Polling Frequency

Adjust `POLL_INTERVAL` in `driver.py`:

python

```
POLL_INTERVAL = 10  # seconds between Twitter checks
```

### Model Configuration

Modify AI model in `langgraphPipe.py`:

python

```
llm = ChatOllama(
    model="llama3.2:latest",
    temperature=0,
    base_url="http://ollama:11434"
)
```

Database Operations
-------------------

### Connect to PostgreSQL

bash

```
psql -h localhost -p 5431 -U ${POSTGRES_USER} -d ${POSTGRES_DB}
```

### Database Schema

-   **`markets`**: Prediction market metadata
-   **`tokens`**: Market outcome tokens with pricing data
-   **`bought`**: Trade execution log with tweet references

Monitoring & Debugging
----------------------

### API Endpoints

-   **Health Check**: `GET http://localhost:8000/db`
-   **Tweet IDs**: `GET http://localhost:8000/tweet-ids`
-   **Market Data**: `POST http://localhost:8000/poly`

### Data Persistence

-   **PostgreSQL**: `./backend_pgdata/` volume
-   **ChromaDB**: `./chroma/` directory
-   **Ollama Models**: `ollama_data` volume
-   **HuggingFace Cache**: `huggingface_cache` volume

Development Challenges
----------------------

### Browser Automation & Anti-Bot Detection

Twitter's anti-bot measures required implementing advanced stealth
