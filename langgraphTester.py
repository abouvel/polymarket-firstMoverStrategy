from langgraphPipe import graph  # Make sure prediction_agent.py is in same directory
from pprint import pprint

# 🟡 Provide a headline to test the pipeline
async def runcom(tweet):
    initial_state = {
        "headline": f"{tweet}",
        "enriched_headline": "",
        "search_results": "",
        "top_k": [],
        "structured_output": {},
        "selected_id": "",
        "token_id": ""
    }

    # ▶️ Run full graph asynchronously
    print("\nRunning LangGraph...\n")
    print(f"Initial state: {initial_state}")
    try:
        final_result = await graph.ainvoke(initial_state)
        print(f"LangGraph completed successfully!")
        print(f"Final result: {final_result}")
    except Exception as e:
        print(f"LangGraph failed with error: {e}")
        print(f"Error type: {type(e).__name__}")
        raise

    print("\nFinal Output:")
    pprint(final_result)
    return final_result

# Main function for testing
async def main():
    test_tweet = "BREAKING: Zohran Mamdani drops 15 points in latest NYC mayoral poll, now trailing by significant margin"
    print(f"Testing LangGraph with tweet: {test_tweet}")
    
    try:
        result = await runcom(test_tweet)
        print(f"\nTest completed successfully!")
        return result
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

