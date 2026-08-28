from __future__ import annotations


class RateLimitError(Exception):
    """Raised when Atlas returns HTTP 429; caller must not retry before retry_after_seconds."""

    def __init__(self, retry_after_seconds: float) -> None:
        super().__init__(f"Rate limited; retry after {retry_after_seconds}s")
        self.retry_after_seconds = retry_after_seconds


class BudgetExhaustedError(Exception):
    """Raised when a journey's call_budget has reached zero."""


class AtlasSearchError(Exception):
    """Raised when Atlas returns a non-zero status or an unexpected HTTP error."""

    def __init__(self, message: str, status_code: int | None = None, atlas_status: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.atlas_status = atlas_status


class SearchRecordNotFoundError(Exception):
    """Raised by get_options() when the requested search_id does not exist in search_records."""

    def __init__(self, search_id: str) -> None:
        super().__init__(f"SearchRecord not found: {search_id}")
        self.search_id = search_id


class ScoringRunNotFoundError(Exception):
    """Raised by get_scoring_run() when the requested run_id does not exist."""

    def __init__(self, run_id: str) -> None:
        super().__init__(f"ScoringRun not found: {run_id}")
        self.run_id = run_id


class AtlasVerifyError(Exception):
    """Raised when Atlas returns a non-zero status or an unexpected HTTP error from verify.do."""

    def __init__(self, message: str, status_code: int | None = None, atlas_status: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.atlas_status = atlas_status


class OptionUnavailableError(Exception):
    """Raised when verify.do reports the selected option is no longer available."""

    def __init__(self, option_id: str) -> None:
        super().__init__(f"Option no longer available: {option_id}")
        self.option_id = option_id
