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


class SessionExpiredError(Exception):
    """Raised when order creation is attempted against an already-expired session (FR-014)."""

    def __init__(self, journey_id: str) -> None:
        super().__init__(f"Session already expired for journey {journey_id!r}; refusing to create order")
        self.journey_id = journey_id


class DuplicateOrderAnomalyError(Exception):
    """Raised when a duplicate-order rejection carries more than one existing order reference (FR-006, research.md R8)."""

    def __init__(self, duplicate_orders: list[str]) -> None:
        super().__init__(f"Expected exactly one duplicate order reference, got: {duplicate_orders}")
        self.duplicate_orders = duplicate_orders


class PaymentDeclinedError(Exception):
    """Raised when payment is attempted again for an order that was already declined (FR-013)."""

    def __init__(self, order_no: str) -> None:
        super().__init__(f"Payment already declined for order {order_no!r}; not retrying")
        self.order_no = order_no


class OrderNotFoundError(Exception):
    """Raised when payment is attempted for a journey with no successfully created order (FR-008)."""

    def __init__(self, order_no: str) -> None:
        super().__init__(f"No successfully created order found: {order_no!r}")
        self.order_no = order_no


class UnregisteredActionTypeError(Exception):
    """Raised when the post-action verification gate is asked to verify an
    action_type with no registered SuccessCondition (spec 012, FR-003)."""

    def __init__(self, action_type: str) -> None:
        super().__init__(f"No SuccessCondition registered for action_type: {action_type!r}")
        self.action_type = action_type


class JourneyNotFoundError(Exception):
    """Raised when an injection targets a journey_id that does not
    correspond to any existing journey (spec 008, research.md R6)."""

    def __init__(self, journey_id: str) -> None:
        super().__init__(f"No journey found: {journey_id!r}")
        self.journey_id = journey_id


class JourneyHasNoOrderError(Exception):
    """Raised when an injection targets a real journey with no order
    carrying a real order_no yet (spec 008, FR-005, research.md R6)."""

    def __init__(self, journey_id: str) -> None:
        super().__init__(f"Journey {journey_id!r} has no real order to reference")
        self.journey_id = journey_id


class InjectorDisabledError(Exception):
    """Raised when the disruption injector is disabled (spec 008, FR-008)."""
