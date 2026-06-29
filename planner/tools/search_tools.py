"""
planner/tools/search_tools.py — Web search tools.
"""

import os
from planner.tools.exceptions import SearchUnavailableError

def search_enabled() -> bool:
    """
    Returns True if TAVILY_API_KEY is set in the environment.
    """
    return bool(os.getenv("TAVILY_API_KEY", "").strip())

def web_search(query: str, max_results: int = 5) -> list[dict]:
    """
    Web search via Tavily API (requires TAVILY_API_KEY in .env).
    Returns list of {title, url, snippet} dicts.
    If TAVILY_API_KEY not set: raises SearchUnavailableError.
    """
    if not search_enabled():
        raise SearchUnavailableError("TAVILY_API_KEY environment variable is not set.")
        
    try:
        from tavily import TavilyClient
        api_key = os.getenv("TAVILY_API_KEY")
        client = TavilyClient(api_key=api_key)
        
        response = client.search(query=query, max_results=max_results)
        results = response.get("results", [])
        
        output = []
        for r in results:
            output.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content") or r.get("snippet", "")
            })
        return output
    except ImportError:
        raise SearchUnavailableError("tavily-python package is not installed.")
    except Exception as exc:
        raise SearchUnavailableError(f"Tavily search API failed: {exc}")
