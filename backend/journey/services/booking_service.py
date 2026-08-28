from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

import httpx

from journey.errors import (
    DuplicateOrderAnomalyError,
    OrderNotFoundError,
    PaymentDeclinedError,
    SessionExpiredError,
)
from journey.models.booking import Order, OrderOutcome, PaymentAttempt, PaymentOutcome, TicketingQuery
from journey.models.journey import JourneyState
from journey.services.state_service import JourneyStateService

if TYPE_CHECKING:
    from journey.storage.repository import JourneyRepository

_ATLAS_ORDER_URL = "https://sandbox.atriptech.com/order.do"
_ATLAS_PAY_URL = "https://sandbox.atriptech.com/pay.do"
_ATLAS_QUERY_URL = "https://sandbox.atriptech.com/queryOrderDetails.do"


class BookingService:
    def __init__(self, repo: "JourneyRepository", http_client: httpx.Client) -> None:
        self._repo = repo
        self._http = http_client
        self._state_service = JourneyStateService(repository=repo)

    # ------------------------------------------------------------------
    # CreateOrder
    # ------------------------------------------------------------------

    def create_order(self, journey_id: str, option_id: str, now: datetime) -> Order:
        session_identifier = self._find_session_identifier(journey_id)
        if now >= session_identifier.stale_at:
            raise SessionExpiredError(journey_id)

        verification = self._repo.get_latest_verification(journey_id, option_id)
        if verification is None:
            raise ValueError(f"No verification found for option {option_id!r}")

        return self._attempt_order(
            journey_id, option_id, session_identifier.value, verification, now, retry_on_uncertain=True
        )

    def _attempt_order(
        self,
        journey_id: str,
        option_id: str,
        session_id: str,
        verification: Any,
        now: datetime,
        retry_on_uncertain: bool,
    ) -> Order:
        request_body = self._build_order_request(session_id, verification)
        requested_at = now

        try:
            response = self._http.post(_ATLAS_ORDER_URL, json=request_body)
        except httpx.HTTPError:
            order = self._build_order(
                journey_id, option_id, session_id, OrderOutcome.UNCERTAIN, requested_at, None, None
            )
            self._repo.save_order(order)
            if retry_on_uncertain:
                return self._resolve_uncertain_order(
                    journey_id, option_id, session_id, verification, now
                )
            return order

        responded_at = now
        try:
            raw_json: dict[str, Any] = response.json()
        except Exception:
            order = self._build_order(
                journey_id, option_id, session_id, OrderOutcome.ERROR, requested_at, responded_at, response.text
            )
            self._repo.save_order(order)
            return order

        raw_str = json.dumps(raw_json)
        status = raw_json.get("status", -1)
        duplicate_orders = raw_json.get("duplicateOrders")

        if status == 0:
            order = self._build_order(
                journey_id,
                option_id,
                session_id,
                OrderOutcome.CREATED,
                requested_at,
                responded_at,
                raw_str,
                order_no=raw_json.get("orderNo"),
                booking_reference=raw_json.get("pnrCode"),
                ticketing_deadline=_parse_dt(raw_json.get("tktLimitTime")),
            )
            self._repo.save_order(order)
            self._on_created(journey_id, order, now)
            return order

        if duplicate_orders:
            if len(duplicate_orders) != 1:
                raise DuplicateOrderAnomalyError(duplicate_orders)
            order = self._build_order(
                journey_id,
                option_id,
                session_id,
                OrderOutcome.DUPLICATE_REJECTED,
                requested_at,
                responded_at,
                raw_str,
                order_no=duplicate_orders[0],
            )
            self._repo.save_order(order)
            self._resolve_duplicate(journey_id, order, now)
            return order

        order = self._build_order(
            journey_id, option_id, session_id, OrderOutcome.ERROR, requested_at, responded_at, raw_str
        )
        self._repo.save_order(order)
        return order

    def _resolve_uncertain_order(
        self, journey_id: str, option_id: str, session_id: str, verification: Any, now: datetime
    ) -> Order:
        """Re-attempt order creation once; a duplicate rejection confirms the
        first attempt succeeded (research.md R3)."""
        return self._attempt_order(
            journey_id, option_id, session_id, verification, now, retry_on_uncertain=False
        )

    def _resolve_duplicate(self, journey_id: str, order: Order, now: datetime) -> None:
        assert order.order_no is not None  # set from duplicateOrders[0] just above
        # _query_order() itself transitions to MONITORING if confirmed.
        self._query_order(journey_id, order.order_no, now)

    def _build_order_request(self, session_id: str, verification: Any) -> dict[str, Any]:
        passenger: dict[str, Any] = {}
        for field in verification.passenger_requirements:
            passenger[field.field_name] = None
        return {
            "cid": "<client id>",
            "sessionId": session_id,
            "passengers": [passenger],
            "contact": {"name": None, "email": None, "mobile": None},
            "requestSource": "antabay",
        }

    def _build_order(
        self,
        journey_id: str,
        option_id: str,
        session_id: str,
        outcome: OrderOutcome,
        requested_at: datetime,
        responded_at: datetime | None,
        raw_response_json: str | None,
        order_no: str | None = None,
        booking_reference: str | None = None,
        ticketing_deadline: datetime | None = None,
    ) -> Order:
        return Order(
            order_id=str(uuid.uuid4()),
            journey_id=journey_id,
            option_id=option_id,
            requested_at=requested_at,
            responded_at=responded_at,
            raw_response_json=raw_response_json,
            outcome=outcome,
            order_no=order_no,
            booking_reference=booking_reference,
            ticketing_deadline=ticketing_deadline,
            session_id_used=session_id,
        )

    def _on_created(self, journey_id: str, order: Order, now: datetime) -> None:
        if order.ticketing_deadline is not None and order.order_no is not None:
            stale_after = (order.ticketing_deadline - now).total_seconds()
            self._state_service.add_held_identifier(
                journey_id=journey_id,
                value=order.order_no,
                issued_at=now,
                stale_after_seconds=int(max(stale_after, 0)),
            )

    # ------------------------------------------------------------------
    # SubmitPayment
    # ------------------------------------------------------------------

    def submit_payment(self, journey_id: str, order_no: str, now: datetime) -> PaymentAttempt:
        order = self._repo.get_order_by_order_no(order_no)
        if order is None or order.outcome is not OrderOutcome.CREATED:
            raise OrderNotFoundError(order_no)

        declined = self._repo.get_declined_payment(order_no)
        if declined is not None:
            raise PaymentDeclinedError(order_no)

        requested_at = now
        try:
            response = self._http.post(_ATLAS_PAY_URL, json={"cid": "<client id>", "orderNo": order_no, "requestSource": "antabay"})
        except httpx.HTTPError:
            payment = self._build_payment(journey_id, order_no, PaymentOutcome.UNCERTAIN, requested_at, None, None)
            self._repo.save_payment(payment)
            return payment

        responded_at = now
        try:
            raw_json: dict[str, Any] = response.json()
        except Exception:
            payment = self._build_payment(
                journey_id, order_no, PaymentOutcome.ERROR, requested_at, responded_at, response.text
            )
            self._repo.save_payment(payment)
            return payment

        raw_str = json.dumps(raw_json)
        status = raw_json.get("status", -1)
        outcome = PaymentOutcome.SUCCESS if status == 0 else PaymentOutcome.DECLINED

        payment = self._build_payment(journey_id, order_no, outcome, requested_at, responded_at, raw_str)
        self._repo.save_payment(payment)
        return payment

    def _build_payment(
        self,
        journey_id: str,
        order_no: str,
        outcome: PaymentOutcome,
        requested_at: datetime,
        responded_at: datetime | None,
        raw_response_json: str | None,
    ) -> PaymentAttempt:
        return PaymentAttempt(
            payment_id=str(uuid.uuid4()),
            journey_id=journey_id,
            order_no=order_no,
            requested_at=requested_at,
            responded_at=responded_at,
            raw_response_json=raw_response_json,
            outcome=outcome,
        )

    # ------------------------------------------------------------------
    # ConfirmTicketing
    # ------------------------------------------------------------------

    def confirm_ticketing(self, journey_id: str, order_no: str, now: datetime) -> TicketingQuery:
        order = self._repo.get_order_by_order_no(order_no)
        if order is None or order.outcome is not OrderOutcome.CREATED:
            raise OrderNotFoundError(order_no)

        deadline_identifier = self._find_ticketing_deadline_identifier(journey_id, order_no)
        if deadline_identifier is not None and now >= deadline_identifier.stale_at:
            existing = self._repo.get_ticketing_queries(order_no)
            if existing:
                return existing[-1]
            return TicketingQuery(
                query_id=str(uuid.uuid4()),
                journey_id=journey_id,
                order_no=order_no,
                queried_at=now,
                raw_response_json="{}",
                confirmed=False,
                is_terminal_error=False,
            )

        return self._query_order(journey_id, order_no, now)

    def _query_order(self, journey_id: str, order_no: str, now: datetime) -> TicketingQuery:
        response = self._http.post(
            _ATLAS_QUERY_URL, json={"cid": "<client id>", "orderNo": order_no, "requestSource": "antabay"}
        )
        raw_json: dict[str, Any] = response.json()
        raw_str = json.dumps(raw_json)

        pax_infos = raw_json.get("paxTicketInfos") or []
        ticket_numbers = [p.get("ticketNos", []) for p in pax_infos]
        confirmed = bool(ticket_numbers) and all(bool(nos) for nos in ticket_numbers)
        is_terminal_error = raw_json.get("errorCode") is not None

        query = TicketingQuery(
            query_id=str(uuid.uuid4()),
            journey_id=journey_id,
            order_no=order_no,
            queried_at=now,
            raw_response_json=raw_str,
            order_status=raw_json.get("orderStatus"),
            ticket_status=raw_json.get("ticketStatus"),
            passenger_ticket_numbers=ticket_numbers,
            confirmed=confirmed,
            is_terminal_error=is_terminal_error,
        )
        self._repo.save_ticketing_query(query)

        if confirmed:
            self._transition_to_monitoring(journey_id, now)

        return query

    def _transition_to_monitoring(self, journey_id: str, now: datetime) -> None:
        journey = self._repo.get_journey(journey_id)
        if journey.state is JourneyState.VERIFIED:
            self._state_service.transition(
                journey_id, JourneyState.MONITORING, reason="ticketing confirmed", now=now
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_session_identifier(self, journey_id: str) -> Any:
        from journey.services.state_service import IdentifierNotFoundError

        journey = self._repo.get_journey(journey_id)
        candidates = sorted(journey.held_identifiers, key=lambda h: h.issued_at)
        for ident in reversed(candidates):
            return ident
        raise IdentifierNotFoundError(f"No session identifier held for journey {journey_id!r}")

    def _find_ticketing_deadline_identifier(self, journey_id: str, order_no: str) -> Any:
        journey = self._repo.get_journey(journey_id)
        for ident in journey.held_identifiers:
            if ident.value == order_no:
                return ident
        return None


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
