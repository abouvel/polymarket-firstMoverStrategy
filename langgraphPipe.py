# prediction_agent.py

from typing import TypedDict
from langgraph.graph import StateGraph, END
from langchain_core.runnables import Runnable
from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain.embeddings import HuggingFaceEmbeddings
from langchain_tavily import TavilySearch
from langchain_community.llms import Ollama
from langchain_ollama import ChatOllama

from langchain_core.prompts import PromptTemplate
import psycopg2
from dotenv import load_dotenv
import os
import json
from pydantic import BaseModel
from langchain_core.output_parsers import PydanticOutputParser
from datetime import datetime

import requests
import csv
url = os.getenv("WEBHOOK_URL", "http://twitter-webhook:8000")
embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")  # 384-dimensional

# --- Dashboard Broadcasting ---
async def broadcast_trade_event(event_type: str, data: dict):
    """Send trade events to dashboard webhook - async HTTP call"""
    try:
        import aiohttp
        payload = {
            "type": event_type,
            "data": data
        }
        # Async HTTP POST to webhook
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{url}/api/broadcast", json=payload, timeout=aiohttp.ClientTimeout(total=1)) as resp:
                pass  # Fire and forget
    except Exception as e:
        print(f"Dashboard broadcast failed: {e}")

# --- Core Components ---

# --- Database Helper Functions ---
def get_db_connection():
    """Create and return a PostgreSQL database connection"""
    load_dotenv()
    try:
        conn = psycopg2.connect(
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            host=os.getenv("POSTGRES_HOST"),
            port=os.getenv("POSTGRES_PORT"),
            dbname=os.getenv("POSTGRES_DB")
        )
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        print(f"Connection details: {os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')} as {os.getenv('POSTGRES_USER')}")
        raise

tavily_api_key = os.getenv("TAVILY_API_KEY")
# ✅ Ensure path and collection match FastAPI setup
chroma_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma")
vectorstore = Chroma(
    persist_directory=chroma_path,
    collection_name="events",
    embedding_function=embedding_model
)
load_dotenv()
llm = ChatOllama(
    model="tinyllama:1.1b",  # Ultra-fast lightweight model
    temperature=0,
    base_url="http://ollama:11434"  # Use Docker service name instead of localhost
)



#structured output for interm step
class MarketChoice(BaseModel):
    selected_number: int
    reasoning: str

model_with_structure = llm.with_structured_output(MarketChoice)

# --- Prompt Template ---
prompt = PromptTemplate.from_template("""
You are an expert in prediction market analysis. The current date is July 2025.

A headline reads:
"{headline}"

Here are 5 active prediction markets:
{markets}

Which market’s odds would change the most in response to this headline?
Pick only one number (1–5).
You are an expert. Do not explain or overthink.
Focus on *impact to the odds*, not player performance uncertainty.
Team-level outcomes generally move more than stat-based or award markets.
Respond confidently and quickly.
""")

# --- Helper Functions ---
def get_top_k_markets(headline: str, k=5):
    # If headline is an AIMessage, extract .content
    if hasattr(headline, "content"):
        headline = headline.content

    return vectorstore.similarity_search_with_score(headline, k=k)

def format_market_choices(results):
    return "\n".join([f"{i+1}. {doc.metadata['name']}" for i, (doc, _) in enumerate(results)])

def make_llm_decision(headline: str, results):
    market_text = format_market_choices(results)
    prompt_input = prompt.format(headline=headline, markets=market_text)
    return llm.invoke(prompt_input)

def make_llm_structured_decision(headline: str, markets, context):
    market_text = format_market_choices(markets)
    input_prompt = f"""
You are an expert in prediction market analysis. The current date is July 2025.

A headline reads:
"{headline}"

You also have access to the following relevant context:
"{context}"

Here are 5 active prediction markets:
{market_text}

Which market’s odds would change the most in response to this headline?
Pick only one number (1–5).

Respond in JSON with:
{{
  "selected_number": <1-5>,
  "reasoning": "...brief explanation..."
}}
"""
    return model_with_structure.invoke(input_prompt)

def search_web_context(query: str, date: str):
    search = TavilySearch(api_key=tavily_api_key, end_date=date)

    return search.invoke({"query": query})

def summarize_headline_with_context(headline: str, context: str) -> str:
    prompt = f"""
You are a neutral news assistant. Your job is to create a clean, factual summary in 1-2 sentences.

Headline: \"{headline}\"
Context: \"{context}\"

Write a clear, neutral summary in 1-2 sentences. Focus on facts only. No analysis, questions, or extra formatting.
"""
    return llm.invoke(prompt).content


def get_market_tokens(market_id: str):
    try:
        print(f"[get_market_tokens] Connecting to PostgreSQL")
        conn = get_db_connection()
        print("[get_market_tokens] PostgreSQL connection successful")
        
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, name FROM tokens
            WHERE market_id = %s
            LIMIT 2
            """,
            (market_id,)
        )
        rows = cursor.fetchall()
        tokens = [{"id": row[0], "name": row[1]} for row in rows]

        cursor.close()
        conn.close()
        return tokens
    except Exception as e:
        print(f"[get_market_tokens] Error fetching tokens: {e}")
        print(f"[get_market_tokens] Error type: {type(e).__name__}")
        return []

def get_historical_price(token_id: str, start_timestamp: int, end_timestamp: int):
    """
    Fetch historical price data from Polymarket API
    GET https://clob.polymarket.com/prices-history?market=TOKEN_ID&startTs=START&endTs=END&fidelity=1
    """
    try:
        url = f"https://clob.polymarket.com/prices-history"
        params = {
            "market": token_id,
            "startTs": start_timestamp,
            "endTs": end_timestamp,
            "fidelity": 1
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        if data and len(data) > 0:
            # Return the last price in the time range
            return float(data[-1].get('price', 0))
        return None
        
    except Exception as e:
        print(f"Error fetching historical price for {token_id}: {e}")
        return None

def write_action_to_csv(action: str, state: dict, trade_data: dict = None):
    """Write trade or skip action to CSV file"""
    csv_filename = 'trades.csv'
    file_exists = os.path.exists(csv_filename)
    
    # Clean tweet text - extract just the text content
    tweet_text = state.get('headline', '')
    if isinstance(tweet_text, str) and tweet_text.startswith("{'id':"):
        try:
            # Extract text from tweet dict string
            import ast
            tweet_dict = ast.literal_eval(tweet_text)
            tweet_text = tweet_dict.get('text', tweet_text)[:200]  # Limit length
        except:
            pass
    
    # Base data from state
    csv_data = {
        'date': state.get('date', ''),
        'tweet': tweet_text,
        'market_name': '',
        'token_name': '',
        'action': action,
        'purchase_price': None,
        'price_24h': None,
        'profit_loss_pct': None,
        'reasoning': state.get('enriched_headline', '')[:300] if state.get('enriched_headline') else '',  # Limit length
        'skip_reason': ''
    }
    
    # Get market name from selected_id
    if state.get('selected_id') and state['selected_id'] != 'unknown_market_0':
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT title FROM markets WHERE id = %s", (state['selected_id'],))
            market_row = cursor.fetchone()
            if market_row:
                csv_data['market_name'] = market_row[0][:100]  # Limit length
            else:
                csv_data['market_name'] = "No matching market found"
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Error getting market name for CSV: {e}")
            csv_data['market_name'] = "Database error"
    else:
        csv_data['market_name'] = "No relevant markets found"
    
    # Add trade-specific data if provided
    if trade_data:
        csv_data.update({
            'token_name': trade_data.get('token_name', ''),
            'purchase_price': trade_data.get('purchase_price'),
            'price_24h': trade_data.get('current_price'),
            'profit_loss_pct': trade_data.get('profit_loss')
        })
    
    # Add skip reason for skipped actions
    if action == 'SKIP':
        csv_data['skip_reason'] = 'Low market impact - tweet not significant enough'
    
    with open(csv_filename, 'a', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['date', 'tweet', 'market_name', 'token_name', 'action', 'purchase_price', 'price_24h', 'profit_loss_pct', 'reasoning', 'skip_reason']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        if not file_exists:
            writer.writeheader()
        
        writer.writerow(csv_data)

def write_backtest_result(csv_filename: str, trade_data: dict):
    """Write backtest results to CSV file - legacy function"""
    file_exists = os.path.exists(csv_filename)
    
    with open(csv_filename, 'a', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['date', 'tweet', 'market_name', 'token_name', 'action', 'purchase_price', 'price_24h', 'profit_loss_pct', 'reasoning']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        if not file_exists:
            writer.writeheader()
        
        writer.writerow(trade_data)

def decide_token_to_trade(structured_output, question,tokens):
    if len(tokens) < 2:
        print("Not enough tokens to make a decision.")
        return None

    reasoning = structured_output.reasoning
    market_question = question


    prompt = f"""
You are an expert market analyst.

Here is a prediction market question:
"{market_question}"

You have two tokens:
1. {tokens[0]['name']}
2. {tokens[1]['name']}

Reasoning: "{reasoning}"

Which token should be bought in response to this reasoning?

Respond with just the number: 1 or 2.
"""

    result = llm.invoke(prompt).content.strip()
    print (tokens)
    if "2" in result:
        return tokens[1]["id"]
    else:
        return tokens[0]["id"]



def execute_trade_on_token(token_id: str, headline: str, buffHeadline: str, trade_date: str = None):
    try:
        print(f"[execute_trade_on_token] Connecting to PostgreSQL")
        conn = get_db_connection()
        print("[execute_trade_on_token] PostgreSQL connection successful")
        
        cursor = conn.cursor()

        # Fetch token name and market ID
        cursor.execute(
            """
            SELECT name, market_id FROM tokens
            WHERE id = %s
            """,
            (token_id,)
        )
        token_row = cursor.fetchone()
        if not token_row:
            print(f"Token with ID {token_id} not found.")
            cursor.close()
            conn.close()
            return

        token_name, market_id = token_row

        # Fetch market name
        cursor.execute(
            """
            SELECT title FROM markets
            WHERE id = %s
            """,
            (market_id,)
        )
        market_row = cursor.fetchone()
        market_name = market_row[0] if market_row else "Unknown Market"
        
        # For backtesting: get historical prices
        purchase_price = None
        current_price = None
        profit_loss = None
        
        if trade_date:
            # Convert trade_date to timestamp
            trade_timestamp = int(datetime.fromisoformat(trade_date).timestamp())
            
            # Get price at purchase time (within 1 hour window)
            purchase_price = get_historical_price(token_id, trade_timestamp - 3600, trade_timestamp + 3600)
            
            # Get price 24 hours later for P&L calculation
            end_timestamp = trade_timestamp + 86400  # +24 hours
            current_price = get_historical_price(token_id, end_timestamp - 3600, end_timestamp + 3600)
            
            if purchase_price and current_price:
                profit_loss = ((current_price - purchase_price) / purchase_price) * 100  # Percentage
        
        # Create comprehensive log entry
        text = f"TRADE: {token_name} | Market: {market_name} | Date: {trade_date}"
        if purchase_price:
            text += f" | Buy: ${purchase_price:.3f}"
        if current_price:
            text += f" | Sell: ${current_price:.3f}"
        if profit_loss is not None:
            text += f" | P&L: {profit_loss:+.2f}%"
        
        print(f"\n{'='*80}")
        print(f"🎯 BACKTEST TRADE EXECUTED")
        print(f"📊 Market: {market_name}")
        print(f"🎫 Token: {token_name}")
        print(f"📅 Date: {trade_date}")
        print(f"📰 Tweet: {headline[:100]}...")
        if purchase_price:
            print(f"💰 Purchase Price: ${purchase_price:.4f}")
        if current_price:
            print(f"💵 Price +24h: ${current_price:.4f}")
        if profit_loss is not None:
            color = "🟢" if profit_loss > 0 else "🔴" if profit_loss < 0 else "🟡"
            print(f"{color} P&L: {profit_loss:+.2f}%")
        print(f"{'='*80}\n")
        
        # Store in database with enhanced schema
        cursor.execute(
            """
            INSERT INTO BOUGHT (TokenID, Tweet, ContextHeadline, Event, Date, PurchasePrice, CurrentPrice, ProfitLoss)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (TokenID) DO UPDATE SET
                Tweet = EXCLUDED.Tweet,
                ContextHeadline = EXCLUDED.ContextHeadline,
                Event = EXCLUDED.Event,
                Date = EXCLUDED.Date,
                PurchasePrice = EXCLUDED.PurchasePrice,
                CurrentPrice = EXCLUDED.CurrentPrice,
                ProfitLoss = EXCLUDED.ProfitLoss
            """,
            (token_id, headline, buffHeadline, text, trade_date, purchase_price, current_price, profit_loss)
        )
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Note: CSV writing is now handled in trade_step() to avoid duplicates
        
        return {"structured_output": f"{text}", "purchase_price": purchase_price, "current_price": current_price, "profit_loss": profit_loss}

    except Exception as e:
        print(f"[execute_trade_on_token] Error during trade execution: {e}")
        print(f"[execute_trade_on_token] Error type: {type(e).__name__}")
        return {"error": str(e)}


# 🔁 STATE
class GraphState(TypedDict):
    headline: str
    enriched_headline: str
    search_results: str
    top_k: list
    structured_output: dict
    selected_id: str
    token_id: str
    date: str
    enriched_date: str  # Added for date enrichment

# 🔍 STEP 1: Search + Enrich Headline

def enrich_headline(state: GraphState):

    
    
    # Convert date to YYYY-MM-DD format
    date_str = state.get("date", "")
    if date_str:
        try:
            parsed_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            formatted_date = parsed_date.strftime("%Y-%m-%d")
        except:
            formatted_date = datetime.now().strftime("%Y-%m-%d")
    else:
        formatted_date = datetime.now().strftime("%Y-%m-%d")
    
    context = search_web_context(state["headline"], formatted_date)
    enriched = summarize_headline_with_context(state["headline"], context)
    print(f"Enriched Headline {enriched}")

    return {
        "search_results": context,
        "enriched_headline": enriched,
        "enriched_date": formatted_date
    }

# 📈 STEP 2: Embed + Search

def embed_and_search(state: GraphState):
    top_k = get_top_k_markets(state["enriched_headline"])
    return {"top_k": top_k}

# 🧠 STEP 3: LLM Market Decision + Structured Output

def decide_market(state: GraphState):
    structured = (make_llm_structured_decision(
        headline=state["headline"],
        markets=state["top_k"],
        context=state["search_results"]
    ))
    selected_index = structured.selected_number - 1
    # Get the selected document from ChromaDB search results
    selected_doc = state["top_k"][selected_index][0]
    
    # The market ID is stored as the ChromaDB document ID, need to get it from the collection
    # For now, we'll use a workaround since ChromaDB similarity_search doesn't return IDs
    print(f"Selected document metadata: {selected_doc.metadata}")
    print(f"Selected document content: {selected_doc.page_content}")
    
    # Try to find the market ID by searching the collection again
    search_results = vectorstore.get(
        where={"name": selected_doc.metadata.get("name")},
        limit=1
    )
    
    if search_results and search_results.get("ids"):
        market_id = search_results["ids"][0]
        print(f"Found market ID: {market_id}")
    else:
        print(f"Could not find market ID for: {selected_doc.metadata.get('name')}")
        market_id = f"unknown_market_{selected_index}"
    return {
        "selected_id": market_id,
        "structured_output": structured
    }

# 🎯 STEP 4: Token Selection

def get_token_to_trade(state: GraphState):
    tokens = get_market_tokens(state["selected_id"])
    token_key = decide_token_to_trade(state["structured_output"],state["enriched_headline"], tokens)
    return {"token_id": token_key}

# 🔍 STEP 5: Significance Check

def check_significance(state: GraphState):
    """Check if the tweet will significantly impact the market odds"""
    tokens = get_market_tokens(state["selected_id"])
    if len(tokens) < 2:
        return "skip"
    
    # Get market name for context
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT title FROM markets WHERE id = %s", (state["selected_id"],))
        market_row = cursor.fetchone()
        market_name = market_row[0] if market_row else "Unknown Market"
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error getting market name: {e}")
        market_name = "Unknown Market"
    
    prompt = f"""
You are an expert market analyst evaluating whether news will significantly impact prediction market odds.
The Date is {state["date"]} take this into consideration and act accordingly.
Tweet: "{state["headline"]}"
Context: "{state["enriched_headline"]}"
Market: "{market_name}"
Reasoning from previous analysis: "{state["structured_output"].reasoning}"

Will this tweet cause a SIGNIFICANT change in the market odds (>5% price movement)?

Consider:
- Is this breaking news or just speculation?
- How directly does it relate to the market outcome?
- Is this information already priced in?
- Would traders immediately react to this news?

Respond with exactly one word: "significant" or "insignificant"
"""
    
    result = llm.invoke(prompt).content.strip().lower()
    if "significant" in result:
        return "execute"
    else:
        return "skip"

# 💸 STEP 6: Trade

async def trade_step(state: GraphState):
    execute_trade_on_token(state["token_id"], state["headline"], state["enriched_headline"], state.get("date"))
    
    # Write trade to CSV using modular function
    write_action_to_csv('BUY', state)
    
    # Broadcast trade executed event
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.name, m.title 
            FROM tokens t 
            JOIN markets m ON t.market_id = m.id 
            WHERE t.id = %s
        """, (state["token_id"],))
        
        result = cursor.fetchone()
        if result:
            token_name, market_name = result
            await broadcast_trade_event("trade_executed", {
                "token_id": state["token_id"],
                "token_name": token_name,
                "market_name": market_name
            })
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error broadcasting trade: {e}")
    
    return {}

# 🚫 STEP 6: Skip Trade

async def skip_trade_step(state: GraphState):
    print(f"Skipping trade - tweet not significant enough for market impact")
    
    # Write skip to CSV using modular function
    write_action_to_csv('SKIP', state)
    
    # Broadcast trade skipped event
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT title FROM markets WHERE id = %s", (state["selected_id"],))
        result = cursor.fetchone()
        market_name = result[0] if result else "Unknown Market"
        
        await broadcast_trade_event("trade_skipped", {
            "reason": "Low market impact - tweet not significant enough",
            "market_name": market_name
        })
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error broadcasting skip: {e}")
    
    return {}


# 🧱 LANGGRAPH CONSTRUCTION
workflow = StateGraph(GraphState)
workflow.add_node("enrich_headline", enrich_headline)
workflow.add_node("embed_and_search", embed_and_search)
workflow.add_node("decide_market", decide_market)
workflow.add_node("get_token_to_trade", get_token_to_trade)
workflow.add_node("trade_step", trade_step)
workflow.add_node("skip_trade_step", skip_trade_step)

workflow.set_entry_point("enrich_headline")
workflow.add_edge("enrich_headline", "embed_and_search")
workflow.add_edge("embed_and_search", "decide_market")
workflow.add_edge("decide_market", "get_token_to_trade")

# Add conditional edge for significance check
workflow.add_conditional_edges(
    "get_token_to_trade",
    check_significance,
    {
        "execute": "trade_step",
        "skip": "skip_trade_step"
    }
)

workflow.add_edge("trade_step", END)
workflow.add_edge("skip_trade_step", END)

graph = workflow.compile()
initial_state = {
    "headline": "Apple announces Tim Cook will retire next year.",
    "enriched_headline": "",
    "search_results": "",
    "top_k": [],
    "structured_output": {},
    "selected_id": "",
    "token_id": "",
}
