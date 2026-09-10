"""Discovery adapters."""

from ardguard.adapters.ard import parse_search_response
from ardguard.adapters.hf_discover import parse_hf_discover_response

__all__ = ["parse_hf_discover_response", "parse_search_response"]
