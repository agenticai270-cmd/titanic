import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from reservations import ReservationManager


class ReservationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.manager = ReservationManager(Path(self.temp_dir.name) / "reservations.json")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_fifo_waitlist_and_fulfillment(self) -> None:
        created = date.today()
        first = self.manager.place_reservation(1, 10, created_on=created)
        second = self.manager.place_reservation(1, 11, created_on=created + timedelta(days=1))
        with self.assertRaisesRegex(ValueError, "Earlier"):
            self.manager.mark_ready(second.reservation_id)
        self.manager.mark_ready(first.reservation_id)
        self.manager.fulfill_reservation(first.reservation_id)
        self.manager.mark_ready(second.reservation_id)
        self.assertEqual(self.manager.reservations[second.reservation_id].state, "ready")

    def test_duplicate_active_reservation_is_rejected(self) -> None:
        self.manager.place_reservation(2, 20)
        with self.assertRaisesRegex(ValueError, "already has"):
            self.manager.place_reservation(2, 20)

    def test_cancel_and_audit_history(self) -> None:
        reservation = self.manager.place_reservation(3, 30)
        self.manager.cancel_reservation(reservation.reservation_id, actor_id=99)
        actions = [entry.action for entry in self.manager.audit_for(reservation.reservation_id)]
        self.assertEqual(actions, ["placed", "cancelled"])

    def test_expiration(self) -> None:
        reservation = self.manager.place_reservation(4, 40, hold_days=1,
                                                     created_on=date(2025, 1, 1))
        expired = self.manager.expire_reservations(date(2025, 1, 3))
        self.assertEqual([item.reservation_id for item in expired], [reservation.reservation_id])
        self.assertEqual(reservation.state, "expired")

    def test_persistence(self) -> None:
        reservation = self.manager.place_reservation(5, 50)
        loaded = ReservationManager(self.manager.data_file)
        self.assertEqual(loaded.reservations[reservation.reservation_id].member_id, 50)
        self.assertEqual(len(loaded.audit_log), 1)

    def test_summary(self) -> None:
        self.manager.place_reservation(6, 60)
        reservation = self.manager.place_reservation(6, 61)
        self.manager.cancel_reservation(reservation.reservation_id)
        summary = self.manager.summary()
        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["waiting"], 1)
        self.assertEqual(summary["cancelled"], 1)


if __name__ == "__main__":
    unittest.main()
