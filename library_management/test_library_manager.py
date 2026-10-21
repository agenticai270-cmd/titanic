import 
import unittest
from datetim timedelta
from pathlib import Path

from library_manager import Library


class LibraryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.library = Library(Path(self.temp_dir.name) / "data.json")
        self.book = self.library.add_book("Dune", "Frank Herbert", 1965, "Science Fiction", 2)
        self.member = self.library.register_member("Asha", "asha@example.com")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_add_search_and_persist_book(self) -> None:
        self.assertEqual(self.library.search_books("herbert")[0].book_id, self.book.book_id)
        loaded = Library(self.library.data_file)
        self.assertEqual(loaded.books[self.book.book_id].category, "Science Fiction")
        self.assertEqual(loaded.books[self.book.book_id].copies, 2)

    def test_legacy_borrowed_by_is_migrated_to_open_loan(self) -> None:
        legacy_file = Path(self.temp_dir.name) / "legacy.json"
        legacy_file.write_text(
            '{"books": [{"book_id": 1, "title": "Dune", '
            '"author": "Frank Herbert", "year": 1965, "borrowed_by": 7}], '
            '"members": [{"member_id": 7, "name": "Asha", '
            '"email": "asha@example.com"}]}',
            encoding="utf-8",
        )
        migrated = Library(legacy_file)
        open_loans = [loan for loan in migrated.loans.values() if loan.is_open]
        self.assertEqual(len(open_loans), 1)
        self.assertEqual(open_loans[0].book_id, 1)
        self.assertEqual(open_loans[0].member_id, 7)

        returned = migrated.return_book(1)
        self.assertIsNotNone(returned.returned_on)
        self.assertEqual(migrated.books[1].available_copies, 1)

    def test_multiple_copies_can_be_borrowed(self) -> None:
        first = self.library.borrow_book(self.book.book_id, self.member.member_id)
        second_member = self.library.register_member("Ravi", "ravi@example.com")
        second = self.library.borrow_book(self.book.book_id, second_member.member_id)
        self.assertNotEqual(first.loan_id, second.loan_id)
        self.assertEqual(self.library.books[self.book.book_id].available_copies, 0)
        with self.assertRaisesRegex(ValueError, "not available"):
            self.library.borrow_book(self.book.book_id, self.member.member_id)

    def test_return_calculates_overdue_fine(self) -> None:
        borrowed = date(2025, 1, 1)
        loan = self.library.borrow_book(self.book.book_id, self.member.member_id,
                                        loan_days=7, borrowed_on=borrowed)
        returned = self.library.return_book(self.book.book_id, date(2025, 1, 10))
        self.assertEqual(returned.loan_id, loan.loan_id)
        self.assertEqual(returned.fine, 2.0)
        self.assertEqual(self.library.books[self.book.book_id].available_copies, 2)

    def test_overdue_and_renewal(self) -> None:
        loan = self.library.borrow_book(self.book.book_id, self.member.member_id,
                                        borrowed_on=date.today() - timedelta(days=20))
        self.assertIn(loan, self.library.overdue_loans())
        old_due_date = loan.due_on
        self.library.renew_loan(loan.loan_id, 5)
        self.assertNotEqual(loan.due_on, old_due_date)

    def test_update_and_remove_book(self) -> None:
        self.library.update_book(self.book.book_id, title="Dune Messiah", copies=3)
        self.assertEqual(self.library.books[self.book.book_id].title, "Dune Messiah")
        self.assertEqual(self.library.books[self.book.book_id].available_copies, 3)
        self.library.remove_book(self.book.book_id)
        self.assertNotIn(self.book.book_id, self.library.books)

    def test_cannot_remove_book_with_active_loan(self) -> None:
        self.library.borrow_book(self.book.book_id, self.member.member_id)
        with self.assertRaisesRegex(ValueError, "active loans"):
            self.library.remove_book(self.book.book_id)

    def test_member_validation_and_deactivation(self) -> None:
        with self.assertRaisesRegex(ValueError, "Email"):
            self.library.register_member("Invalid", "not-an-email")
        self.library.update_member(self.member.member_id, active=False)
        with self.assertRaisesRegex(ValueError, "inactive"):
            self.library.borrow_book(self.book.book_id, self.member.member_id)

    def test_statistics_and_popular_books(self) -> None:
        self.library.borrow_book(self.book.book_id, self.member.member_id)
        stats = self.library.statistics()
        self.assertEqual(stats["titles"], 1)
        self.assertEqual(stats["total_copies"], 2)
        self.assertEqual(stats["active_loans"], 1)
        self.assertEqual(self.library.popular_books()[0][1], 1)

    def test_csv_exports(self) -> None:
        books_file = Path(self.temp_dir.name) / "books.csv"
        loans_file = Path(self.temp_dir.name) / "loans.csv"
        self.library.borrow_book(self.book.book_id, self.member.member_id)
        self.library.export_books_csv(books_file)
        self.library.export_loans_csv(loans_file)
        with books_file.open(newline="", encoding="utf-8") as file:
            self.assertEqual(next(csv.DictReader(file))["title"], "Dune")
        with loans_file.open(newline="", encoding="utf-8") as file:
            self.assertEqual(next(csv.DictReader(file))["member_id"], str(self.member.member_id))


if __name__ == "__main__":
    unittest.main()
