# prediction_agent.py

from typing import TypedDict
from langgraph.graph import StateGraph, END
from langchain_core.runnables import Runnable
from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain.embeddings import HuggingFaceEmbeddings
from langchain_community.tools.tavily_search.tool import TavilySearchResults
from langchain_community.llms import Ollama
from langchain_ollama import ChatOllama

from langchain_core.prompts import PromptTemplate
import psycopg2
from dotenv import load_dotenv
import os
import json
from pydantic import BaseModel
from langchain_core.output_parsers import PydanticOutputParser

import requests

# --- Core Components ---
url = "http://localhost:8000"
embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")  # 384-dimensional

tavily_api_key = os.getenv("TAVILY_API_KEY")
# ✅ Ensure path and collection match FastAPI setup
chroma_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma")
vectorstore = Chroma(
    persist_directory=chroma_path,
    collection_name="events",
    embedding_function=embedding_model
)
load_dotenv()
llm = ChatOllama(model="llama3.2:latest",temperature=0)  # Replace with actual model like "llama3-instruct"
search = TavilySearchResults(tavily_api_key=tavily_api_key)



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

def search_web_context(query: str):
    return search.invoke({"query": query})

def summarize_headline_with_context(headline: str, context: str) -> str:
    prompt = f"""
You are a neutral news assistant. Your job is to rephrase news headlines and related context into clear, factual summaries.

Important:
- Do not reject any headline.
- You are NOT making judgments, promoting content, or offering advice.
- You are ONLY restating a headline and context in plain language.
- You may reword sensitive topics, but do not censor or editorialize.

Headline:
\"{headline}\"

Context:
\"{context}\"

Now, rewrite this as a clear, neutral sentence suitable for internal analysis. Avoid ambiguity. Just report the facts.
"""
    return llm.invoke(prompt).content


def get_market_tokens(market_id: str):
    
    load_dotenv()

    try:
        conn = psycopg2.connect(
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            host=os.getenv("POSTGRES_HOST"),
            port=os.getenv("POSTGRES_PORT"),
            dbname=os.getenv("POSTGRES_DB")
        )
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
        print(f"❌ Error fetching tokens: {e}")
        return []

def decide_token_to_trade(structured_output, question,tokens):
    if len(tokens) < 2:
        print("⚠️ Not enough tokens to make a decision.")
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



def execute_trade_on_token(token_id: str, headline: str, buffHeadline: str):
    load_dotenv()
    try:
        conn = psycopg2.connect(
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            host=os.getenv("POSTGRES_HOST"),
            port=os.getenv("POSTGRES_PORT"),
            dbname=os.getenv("POSTGRES_DB")
        )
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
            print(f"❌ Token with ID {token_id} not found.")
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
        text = f" Executing trade on token \"{token_name}\" from market \"{market_name}\""
        print(text)
        cursor.execute(
            """
            INSERT INTO BOUGHT (TokenID, Tweet, ContextHeadline, Event)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (TokenID) DO NOTHING
            """,
            (token_id, headline, buffHeadline, text)  # ← swapped here
        )

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"❌ Error during trade execution: {e}")


# 🔁 STATE
class GraphState(TypedDict):
    headline: str
    enriched_headline: str
    search_results: str
    top_k: list
    structured_output: dict
    selected_id: str
    token_id: str

# 🔍 STEP 1: Search + Enrich Headline

def enrich_headline(state: GraphState):
    context = search_web_context(state["headline"])
    enriched = summarize_headline_with_context(state["headline"], context)
    print(f"Enriched Headline {enriched}")
    return {
        "search_results": context,
        "enriched_headline": enriched
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
    market_id = state["top_k"][selected_index][0].metadata["id"]
    return {
        "selected_id": market_id,
        "structured_output": structured
    }

# 🎯 STEP 4: Token Selection

def get_token_to_trade(state: GraphState):
    tokens = get_market_tokens(state["selected_id"])
    token_key = decide_token_to_trade(state["structured_output"],state["enriched_headline"], tokens)
    return {"token_id": token_key}

# 💸 STEP 5: Trade

def trade_step(state: GraphState):
    execute_trade_on_token(state["token_id"],state["headline"], state["enriched_headline"])
    return {}


# 🧱 LANGGRAPH CONSTRUCTION
workflow = StateGraph(GraphState)
workflow.add_node("enrich_headline", enrich_headline)
workflow.add_node("embed_and_search", embed_and_search)
workflow.add_node("decide_market", decide_market)
workflow.add_node("get_token_to_trade", get_token_to_trade)
workflow.add_node("trade_step", trade_step)

workflow.set_entry_point("enrich_headline")
workflow.add_edge("enrich_headline", "embed_and_search")
workflow.add_edge("embed_and_search", "decide_market")
workflow.add_edge("decide_market", "get_token_to_trade")
workflow.add_edge("get_token_to_trade", "trade_step")
workflow.add_edge("trade_step", END)

graph = workflow.compile()
initial_state = {
    "headline": "Apple announces Tim Cook will retire next year.",
    "enriched_headline": "",
    "search_results": "",
    "top_k": [],
    "structured_output": {},
    "selected_id": "",
    "token_id": ""
}
