"""Reservation and waitlist support for the library system.

This module is deliberately independent from the command-line interface.  It
can be used by a web API, a desktop application, or the existing CLI without
duplicating reservation rules in each user interface.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


RESERVATION_STATES = {"waiting", "ready", "fulfilled", "cancelled", "expired"}


@dataclass
class Reservation:
    reservation_id: int
    book_id: int
    member_id: int
    created_on: str
    expires_on: str
    state: str = "waiting"
    notified_on: str | None = None
    fulfilled_on: str | None = None
    cancelled_on: str | None = None

    @property
    def is_active(self) -> bool:
        return self.state in {"waiting", "ready"}

    @property
    def is_expired(self) -> bool:
        return date.today() > date.fromisoformat(self.expires_on)


@dataclass
class AuditEntry:
    entry_id: int
    action: str
    reservation_id: int
    actor_id: int | None
    created_at: str
    details: str = ""


class ReservationManager:
    """Maintain FIFO reservations and a durable audit trail."""

    def __init__(self, data_file: str | Path = "reservation_data.json") -> None:
        self.data_file = Path(data_file)
        self.reservations: dict[int, Reservation] = {}
        self.audit_log: list[AuditEntry] = []
        self._load()

    # Persistence ---------------------------------------------------------
    def _load(self) -> None:
        if not self.data_file.exists():
            return
        with self.data_file.open("r", encoding="utf-8") as file:
            data = json.load(file)
        self.reservations = {
            int(item["reservation_id"]): Reservation(**item)
            for item in data.get("reservations", [])
        }
        self.audit_log = [AuditEntry(**item) for item in data.get("audit_log", [])]

    def save(self) -> None:
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": 1,
            "reservations": [asdict(item) for item in self.reservations.values()],
            "audit_log": [asdict(item) for item in self.audit_log],
        }
        temporary_file = self.data_file.with_suffix(self.data_file.suffix + ".tmp")
        with temporary_file.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=2)
        temporary_file.replace(self.data_file)

    @staticmethod
    def _next_id(items: dict[int, Any] | list[Any]) -> int:
        if isinstance(items, dict):
            return max(items, default=0) + 1
        return len(items) + 1

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat(timespec="seconds")

    def _record(self, action: str, reservation_id: int, actor_id: int | None,
                details: str = "") -> None:
        self.audit_log.append(AuditEntry(
            entry_id=self._next_id(self.audit_log), action=action,
            reservation_id=reservation_id, actor_id=actor_id,
            created_at=self._now(), details=details,
        ))

    def _require(self, reservation_id: int) -> Reservation:
        if reservation_id not in self.reservations:
            raise ValueError("Reservation not found.")
        return self.reservations[reservation_id]

    # Reservation lifecycle ----------------------------------------------
    def place_reservation(self, book_id: int, member_id: int,
                          hold_days: int = 3,
                          created_on: date | None = None) -> Reservation:
        """Place a member at the end of a book's waitlist."""
        if book_id <= 0 or member_id <= 0:
            raise ValueError("Book and member IDs must be positive.")
        if hold_days <= 0:
            raise ValueError("Hold days must be positive.")
        if any(
            item.book_id == book_id
            and item.member_id == member_id
            and item.is_active
            for item in self.reservations.values()
        ):
            raise ValueError("Member already has an active reservation for this book.")
        created_on = created_on or date.today()
        reservation = Reservation(
            reservation_id=self._next_id(self.reservations),
            book_id=book_id,
            member_id=member_id,
            created_on=created_on.isoformat(),
            expires_on=(created_on + timedelta(days=hold_days)).isoformat(),
        )
        self.reservations[reservation.reservation_id] = reservation
        self._record("placed", reservation.reservation_id, member_id)
        self.save()
        return reservation

    def cancel_reservation(self, reservation_id: int,
                           actor_id: int | None = None) -> Reservation:
        reservation = self._require(reservation_id)
        if not reservation.is_active:
            raise ValueError("Only active reservations can be cancelled.")
        reservation.state = "cancelled"
        reservation.cancelled_on = self._now()
        self._record("cancelled", reservation_id, actor_id)
        self.save()
        return reservation

    def mark_ready(self, reservation_id: int,
                   actor_id: int | None = None) -> Reservation:
        """Mark the next waiting reservation as ready for collection."""
        reservation = self._require(reservation_id)
        if reservation.state != "waiting":
            raise ValueError("Only waiting reservations can be marked ready.")
        if reservation.is_expired:
            reservation.state = "expired"
            sel
        return reservation

    def dy":
            raise ValueError("Only ready reservations can be fulfilled.")
        reservation.state = "fulfilled"
        reservation.fulfilled_on = self._now()
        self._record("fulfilled", reservation_id, actor_id)
        self.save()
        return reservation

    def expire_reservations(self, as_of: date | None = None) -> list[Reservation]:
        """Expire all waiting/ready holds past their collection deadline."""
        as_of = as_of or date.today()
        expired: list[Reservation] = []
        for reservation in self.reservations.values():
            if reservation.is_active and as_of > date.fromisoformat(reservation.expires_on):
                reservation.state = "expired"
                self._record("expired", reservation.reservation_id, None)
                expired.append(reservation)
        if expired:
            self.save()
        return expired

    # Queries -------------------------------------------------------------
    def _is_first_waiting(self, reservation: Reservation) -> bool:
        waiting = self.waiting_list(reservation.book_id)
        return bool(waiting) and waiting[0].reservation_id == reservation.reservation_id

    def waiting_list(self, book_id: int) -> list[Reservation]:
        return sorted(
            [item for item in self.reservations.values()
             if item.book_id == book_id and item.state == "waiting"],
            key=lambda item: (item.created_on, item.reservation_id),
        )

    def active_for_member(self, member_id: int) -> list[Reservation]:
        return [item for item in self.reservations.values()
                if item.member_id == member_id and item.is_active]

    def active_for_book(self, book_id: int) -> list[Reservation]:
        return [item for item in self.reservations.values()
                if item.book_id == book_id and item.is_active]

    def history_for_member(self, member_id: int) -> list[Reservation]:
        return [item for item in self.reservations.values()
                if item.member_id == member_id]

    def search(self, *, book_id: int | None = None,
               member_id: int | None = None,
               state: str | None = None) -> list[Reservation]:
        if state is not None and state not in RESERVATION_STATES:
            raise ValueError(f"State must be one of: {', '.join(sorted(RESERVATION_STATES))}.")
        return [item for item in self.reservations.values()
                if (book_id is None or item.book_id == book_id)
                and (member_id is None or item.member_id == member_id)
                and (state is None or item.state == state)]

    def audit_for(self, reservation_id: int) -> list[AuditEntry]:
        self._require(reservation_id)
        return [item for item in self.audit_log if item.reservation_id == reservation_id]

    def summary(self) -> dict[str, int]:
        return {
            "total": len(self.reservations),
            "waiting": sum(item.state == "waiting" for item in self.reservations.values()),
            "ready": sum(item.state == "ready" for item in self.reservations.values()),
            "fulfilled": sum(item.state == "fulfilled" for item in self.reservations.values()),
            "cancelled": sum(item.state == "cancelled" for item in self.reservations.values()),
            "expired": sum(item.state == "expired" for item in self.reservations.values()),
        }
