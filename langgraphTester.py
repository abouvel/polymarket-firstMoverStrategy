from langgraphPipe import graph  # Make sure prediction_agent.py is in same directory
from pprint import pprint

# 🟡 Provide a headline to test the pipeline
def runcom(tweet):
    initial_state = {
        "headline": f"{tweet}",
        "enriched_headline": "",
        "search_results": "",
        "top_k": [],
        "structured_output": {},
        "selected_id": "",
        "token_id": ""
    }

    # ▶️ Run full graph
    print("\n🚀 Running LangGraph...\n")
    final_result = graph.invoke(initial_state)

    print("\n✅ Final Output:")
    pprint(final_result)

