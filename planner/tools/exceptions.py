"""
planner/tools/exceptions.py — Tool registry exceptions.
"""

class OverwriteProtectionError(Exception):
    """Raised when write_file is called on a non-empty file with overwrite=False."""
    pass

class ReadOnlyFileError(Exception):
    """Raised when write_file attempts to overwrite RawIdea.md."""
    pass

class LLMCallError(Exception):
    """Raised when an LLM call fails due to timeout, API error, or empty response."""
    pass

LLMConfigError = LLMCallError

class LLMParseError(Exception):
    """Raised when llm_call_json fails to parse the response as valid JSON."""
    pass

class InvalidStatusError(Exception):
    """Raised when update_file_status receives an invalid status symbol."""
    pass

class SearchUnavailableError(Exception):
    """Raised when web_search is called but TAVILY_API_KEY is not set."""
    pass
