# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an AI-powered prediction market trading system that monitors Twitter for market-relevant content, processes it through an AI pipeline, and executes trades on Polymarket based on LLM analysis.

## Development Commands

### Docker Operations
```bash
# Start all services (database, ollama, webhook server, driver)
docker-compose up -d

# Stop and clean up all services
docker-compose down

# View service status
docker-compose ps

# Check service logs
docker-compose logs [service-name]
```

### Service Management
```bash
# Run FastAPI webhook server locally (requires database and ollama running)
uvicorn twitterWebhook:app --host 0.0.0.0 --port 8000 --reload

# Run Twitter scraper manually
python driver.py

# Test LangGraph pipeline
python langgraphTester.py

# Monitor Polymarket WebSocket feeds
python websocketPoly.py
```

### Database Operations
```bash
# Connect to PostgreSQL
psql -h localhost -p 5431 -U ${POSTGRES_USER} -d ${POSTGRES_DB}

# View database structure (see dbStruct.txt for schema)
# Tables: markets, tokens, bought
```

## Architecture Overview

### Core Components
- **`driver.py`** - Twitter scraper using nodriver (Chrome automation) that sends content to webhook
- **`twitterWebhook.py`** - FastAPI server that receives tweets, stores in ChromaDB, and triggers AI pipeline  
- **`langgraphPipe.py`** - Multi-step LangGraph workflow that enriches content, finds relevant markets via vector search, and makes trading decisions
- **`websocketPoly.py`** - Real-time Polymarket price feed subscriber that maintains current bid/ask data

### Data Flow
1. Twitter content → `driver.py` → FastAPI webhook → ChromaDB storage
2. New tweets trigger `langgraphPipe.py` AI pipeline:
   - Web search enrichment (Tavily API)
   - Vector similarity search for relevant prediction markets
   - LLM-based trading decision using structured output
   - Trade execution logging to PostgreSQL
3. `websocketPoly.py` maintains real-time market prices independently

### Key Dependencies
- **External APIs**: Polymarket (trading), Tavily (web search), Twitter (scraping target)
- **AI Stack**: Ollama (llama3.2:latest), HuggingFace embeddings (all-MiniLM-L6-v2), LangGraph/LangChain
- **Databases**: PostgreSQL (structured data), ChromaDB (vector search)
- **Automation**: nodriver (Chrome browser automation)

## Environment Configuration

Required environment variables in `.env`:
```
# Database
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password  
POSTGRES_HOST=localhost
POSTGRES_PORT=5431
POSTGRES_DB=your_db

# APIs
TAVILY_API_KEY=your_tavily_key
POLY_KEY=your_polymarket_key
POLY_ADDRESS=your_polymarket_address
API_KEY=your_websocket_key
API_SECRET=your_websocket_secret
API_PASSPHRASE=your_websocket_passphrase
```

## Docker Service Dependencies

Services start in dependency order:
1. `postgres` + `ollama` (independent)
2. `twitter-webhook` (depends on postgres + ollama)
3. `driver` (depends on twitter-webhook + postgres + ollama)

**Important**: The system pre-downloads HuggingFace models during startup to prevent FastAPI hanging. Git is installed in containers to handle git-based pip dependencies in requirements.txt.

## Database Schema

### PostgreSQL Tables
- **`markets`** - Prediction market metadata
  - Example: ID (hex), Title ("Will 8+ Fed rate cuts happen in 2025?"), Expiry Date (2025-12-10)
- **`tokens`** - Market outcome tokens with pricing data
  - Example: ID (large integer), Market ID (hex), Name ("Yes"), Bid Price, Ask Price
- **`bought`** - Trade execution log (see dbStruct.txt for complete schema)
  - `TokenID` TEXT PRIMARY KEY
  - `Tweet` TEXT NOT NULL  
  - `Date` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP

### ChromaDB Collections (stored in ./chroma directory)
- **`tweets`** - Tweet content with metadata for similarity search
  - Documents: tweet text content
  - Metadata: username, url
  - IDs: tweet_id
  - Accessed via `/receive` endpoint when new tweets arrive
- **`events`** - Polymarket event data for vector similarity matching
  - Documents: event names/slugs
  - Metadata: event name
  - IDs: event_id (hex format)
  - Populated via `/poly` endpoint and used by LangGraph pipeline for market matching

## Development Notes

- FastAPI server runs on port 8000 with hot reload
- Ollama serves on port 11434 for local LLM inference  
- PostgreSQL accessible on port 5431 (mapped from container 5432)
- HuggingFace models cached in persistent Docker volume
- Chrome profiles persist for Twitter authentication
- WebSocket connections handle real-time market data updates