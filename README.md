# AI-Powered Polymarket Trading Bot

An intelligent prediction market trading system that monitors Twitter for market-relevant content, processes it through an AI pipeline, and executes automated trades on Polymarket based on LLM analysis.

**🎥 Demo Video**: [Watch the system in action](https://www.youtube.com/watch?v=6-y4AuxsqeA)

## 🚀 What This Project Does

This system combines social media monitoring, AI analysis, and automated trading to capitalize on prediction market opportunities:

1. **Twitter Monitoring**: Automatically scrapes Twitter content from specified accounts using browser automation
2. **AI Content Analysis**: Processes tweets through a multi-step LangGraph pipeline that enriches content with web search and performs market relevance analysis
3. **Vector Search Matching**: Uses ChromaDB to find relevant prediction markets based on tweet content similarity
4. **Automated Trading**: Makes informed trading decisions using LLaMA 3.2 and executes trades on Polymarket
5. **Real-time Price Tracking**: Maintains current bid/ask prices via WebSocket connections

## 🛠️ Tech Stack

### AI & Machine Learning
- **LangGraph**: Multi-step AI workflow orchestration
- **LangChain**: LLM framework and integrations
- **Ollama**: Local LLM inference (LLaMA 3.2)
- **HuggingFace Transformers**: Text embeddings (all-MiniLM-L6-v2)
- **ChromaDB**: Vector database for semantic search

### Backend & APIs
- **FastAPI**: High-performance webhook server
- **PostgreSQL**: Structured data storage (markets, trades)
- **Tavily**: Web search enrichment API
- **Polymarket API**: Trading execution and market data

### Automation & Data Collection
- **nodriver**: Chrome browser automation for Twitter scraping
- **WebSockets**: Real-time Polymarket price feeds
- **Docker Compose**: Multi-service orchestration

### Development Tools
- **Docker**: Containerized deployment
- **Python 3.x**: Primary development language
- **Async/Await**: Concurrent processing

## 📋 Prerequisites

- Docker and Docker Compose
- Python 3.8+
- Git
- Chrome browser (for automation)

## ⚙️ Environment Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd polyAi/src/backend/expStuff
   ```

2. **Create environment file**:
   ```bash
   cp .env.example .env
   ```

3. **Configure environment variables** in `.env`:
   ```env
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

## 🐳 Running with Docker (Recommended)

### Start All Services
```bash
# Start database, AI services, webhook server, and Twitter scraper
docker-compose up -d

# View service status
docker-compose ps

# Check logs
docker-compose logs -f [service-name]
```

### Stop Services
```bash
# Stop and clean up
docker-compose down

# Stop with volume cleanup
docker-compose down -v
```

## 🔧 Manual Development Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start Core Services
```bash
# Start PostgreSQL and Ollama
docker-compose up -d postgres ollama
```

### 3. Run Components Individually

**Start FastAPI webhook server**:
```bash
uvicorn twitterWebhook:app --host 0.0.0.0 --port 8000 --reload
```

**Run Twitter scraper**:
```bash
python driver.py
```

**Test AI pipeline**:
```bash
python langgraphTester.py
```

**Monitor Polymarket prices**:
```bash
python websocketPoly.py
```

## 📊 Database Operations

### Connect to PostgreSQL
```bash
psql -h localhost -p 5431 -U ${POSTGRES_USER} -d ${POSTGRES_DB}
```

### Database Schema
- **`markets`**: Prediction market metadata (ID, title, expiry)
- **`tokens`**: Market outcome tokens with pricing data
- **`bought`**: Trade execution log with tweet references

## 🔄 System Architecture

### Data Flow
```
Twitter Content → driver.py → FastAPI Webhook → ChromaDB Storage
                                    ↓
ChromaDB → LangGraph Pipeline → Market Analysis → Trade Execution
                ↓                        ↓
        Web Search Enhancement    PostgreSQL Logging
```

### Core Components

1. **`driver.py`**: Twitter scraper using Chrome automation
2. **`twitterWebhook.py`**: FastAPI server handling tweet ingestion
3. **`langgraphPipe.py`**: AI analysis pipeline with structured outputs
4. **`websocketPoly.py`**: Real-time market price monitoring

### AI Pipeline Steps
1. **Content Enrichment**: Web search via Tavily API
2. **Vector Similarity**: ChromaDB semantic matching
3. **Market Analysis**: LLM-based relevance scoring
4. **Trade Decision**: Structured output with reasoning
5. **Execution Logging**: PostgreSQL trade records

## 🎯 Configuration Options

### Monitored Twitter Users
Edit `MONITORED_USERS` in `driver.py`:
```python
MONITORED_USERS = ["username1", "username2", "username3"]
```

### Polling Frequency
Adjust `POLL_INTERVAL` in `driver.py`:
```python
POLL_INTERVAL = 10  # seconds between Twitter checks
```

### Model Configuration
Modify AI model in `langgraphPipe.py`:
```python
llm = ChatOllama(
    model="llama3.2:latest",  # Change model here
    temperature=0,
    base_url="http://ollama:11434"
)
```

## 🔍 Monitoring & Debugging

### Service Health Checks
```bash
# Check all service status
docker-compose ps

# View real-time logs
docker-compose logs -f

# Check specific service
docker-compose logs twitter-webhook
```

### API Endpoints
- **Health Check**: `GET http://localhost:8000/db`
- **Tweet IDs**: `GET http://localhost:8000/tweet-ids`
- **Market Data**: `POST http://localhost:8000/poly`

### Data Persistence
- **PostgreSQL**: `./backend_pgdata/` volume
- **ChromaDB**: `./chroma/` directory
- **Ollama Models**: `ollama_data` volume
- **HuggingFace Cache**: `huggingface_cache` volume

## ⚠️ Important Notes

### Security Considerations
- Never commit API keys or credentials to version control
- Use strong PostgreSQL passwords
- Secure your Polymarket wallet and API access
- Review Twitter automation compliance

### Performance Optimization
- HuggingFace models are pre-downloaded during container startup
- ChromaDB uses persistent storage for vector embeddings
- WebSocket connections maintain real-time price data
- Chrome profiles persist for Twitter authentication

### Error Handling
- Automatic retries for network failures
- Health checks for service dependencies
- Graceful degradation when external APIs are unavailable
- Comprehensive logging for debugging

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with `docker-compose up -d`
5. Submit a pull request

## 📄 License

This project is for educational and research purposes. Please ensure compliance with:
- Twitter's Terms of Service
- Polymarket's API Terms
- Local financial regulations
- Responsible AI usage guidelines

---

**⚡ Quick Start**: `docker-compose up -d` and you're running an AI-powered trading system!
