"""A dependency-free, JSON-backed library management system."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

DEFAULT_LOAN_DAYS = 14
DAILY_FINE = 1.0


@dataclass
class Book:
    book_id: int
    title: str
    author: str
    year: int
    category: str = "General"
    copies: int = 1
    available_copies: int = 1


@dataclass
class Member:
    member_id: int
    name: str
    email: str
    role: str = "member"
    active: bool = True


@dataclass
class Loan:
    loan_id: int
    book_id: int
    member_id: int
    borrowed_on: str
    due_on: str
    returned_on: str | None = None
    fine: float = 0.0

    @property
    def is_open(self) -> bool:
        return self.returned_on is None


class Library:
    """Manage books, members, loans, reports, exports, and persistence."""

    def __init__(self, data_file: str | Path = "library_data.json") -> None:
        self.data_file = Path(data_file)
        self.books: dict[int, Book] = {}
        self.members: dict[int, Member] = {}
        self.loans: dict[int, Loan] = {}
        self._load()

    def _load(self) -> None:
        if not self.data_file.exists():
            return
        with self.data_file.open("r", encoding="utf-8") as file:
            data = json.load(file)
        legacy_books = data.get("books", [])
        self.books = {
            int(item["book_id"]): self._book_from_dict(item)
            for item in legacy_books
        }
        self.members = {
            int(item["member_id"]): Member(**item)
            for item in data.get("members", [])
        }
        self.loans = {
            int(item["loan_id"]): Loan(**item)
            for item in data.get("loans", [])
        }
        self._migrate_legacy_loans(legacy_books)

    def _migrate_legacy_loans(self, legacy_books: list[dict[str, Any]]) -> None:
        """Convert legacy ``borrowed_by`` values into open loan records."""
        migrated = False
        today = date.today()
        for item in legacy_books:
            borrowed_by = item.get("borrowed_by")
            if borrowed_by is None:
                continue
            book_id = int(item["book_id"])
            member_id = int(borrowed_by)
            if book_id not in self.books or member_id not in self.members:
                continue
            if any(
                loan.book_id == book_id
                and loan.member_id == member_id
                and loan.is_open
                for loan in self.loans.values()
            ):
                continue
            loan = Loan(
                loan_id=self._next_id(self.loans),
                book_id=book_id,
                member_id=member_id,
                borrowed_on=today.isoformat(),
                due_on=(today + timedelta(days=DEFAULT_LOAN_DAYS)).isoformat(),
            )
            self.loans[loan.loan_id] = loan
            migrated = True
        if migrated:
            self.save()

    @staticmethod
    def _book_from_dict(item: dict[str, Any]) -> Book:
        copies = int(item.get("copies", 1))
        available = "]), title=item["title"], author=item["author"],
            year=int(item["year"]), category=item.get("category", "General"),
            copies=copies, available_copies=int(available),
        )

    def save(self) -> None:
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": 2,
            "books": [asdict(book) for book in self.books.values()],
            "members": [asdict(member) for member in self.members.values()],
            "loans": [asdict(loan) for loan in self.loans.values()],
        }
        temporary_file = self.data_file.with_suffix(self.data_file.suffix + ".tmp")
        with temporary_file.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=2)
        temporary_file.replace(self.data_file)

    @staticmethod
    def _next_id(items: dict[int, Any]) -> int:
        return max(items, default=0) + 1

    @staticmethod
    def _text(value: str, field_name: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError(f"{field_name} is required.")
        return value

    @staticmethod
    def _positive(value: int, field_name: str) -> int:
        if value <= 0:
            raise ValueError(f"{field_name} must be positive.")
        return value

    def _require_book(self, book_id: int) -> Book:
        if book_id not in self.books:
            raise ValueError("Book not found.")
        return self.books[book_id]

    def _require_member(self, member_id: int) -> Member:
        if member_id not in self.members:
            raise ValueError("Member not found.")
        return self.members[member_id]

    # Book operations -----------------------------------------------------
    def add_book(self, title: str, author: str, year: int,
                 category: str = "General", copies: int = 1) -> Book:
        title = self._text(title, "Title")
        author = self._text(author, "Author")
        category = self._text(category, "Category")
        if year < 0:
            raise ValueError("Year cannot be negative.")
        copies = self._positive(copies, "Copies")
        book = Book(self._next_id(self.books), title, author, year,
                    category, copies, copies)
        self.books[book.book_id] = book
        self.save()
        return book

    def update_book(self, book_id: int, **changes: Any) -> Book:
        book = self._require_book(book_id)
        allowed = {"title", "author", "year", "category", "copies"}
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(f"Unknown book fields: {', '.join(sorted(unknown))}.")
        for key in ("title", "author", "category"):
            if key in changes:
                changes[key] = self._text(str(changes[key]), key.title())
        if "year" in changes and int(changes["year"]) < 0:
            raise ValueError("Year cannot be negative.")
        if "copies" in changes:
            new_copies = self._positive(int(changes["copies"]), "Copies")
            borrowed = book.copies - book.available_copies
            if new_copies < borrowed:
                raise ValueError("Copies cannot be fewer than borrowed copies.")
            book.available_copies = new_copies - borrowed
            changes["copies"] = new_copies
        for key, value in changes.items():
            setattr(book, key, value)
        self.save()
        return book

    def remove_book(self, book_id: int) -> None:
        book = self._require_book(book_id)
        if book.available_copies != book.copies:
            raise ValueError("Cannot remove a book with active loans.")
        del self.books[book_id]
        self.save()

    def search_books(self, query: str = "", category: str | None = None,
                     available_only: bool = False) -> list[Book]:
        query = query.strip().lower()
        category = category.strip().lower() if category else None
        return [
            book for book in self.books.values()
            if (not query or query in book.title.lower() or query in book.author.lower())
            and (not category or book.category.lower() == category)
            and (not available_only or book.available_copies > 0)
        ]

    def categories(self) -> list[str]:
        return sorted({book.category for book in self.books.values()})

    # Member operations --------------------------------------------------
    def register_member(self, name: str, email: str,
                        role: str = "member") -> Member:
        name = self._text(name, "Name")
        email = self._text(email, "Email")
        role = self._text(role, "Role").lower()
        if "@" not in email:
            raise ValueError("Email must contain '@'.")
        if role not in {"member", "librarian", "admin"}:
            raise ValueError("Role must be member, librarian, or admin.")
        member = Member(self._next_id(self.members), name, email, role)
        self.members[member.member_id] = member
        self.save()
        return member

    def update_member(self, member_id: int, **changes: Any) -> Member:
        member = self._require_member(member_id)
        allowed = {"name", "email", "role", "active"}
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(f"Unknown member fields: {', '.join(sorted(unknown))}.")
        if "name" in changes:
            changes["name"] = self._text(str(changes["name"]), "Name")
        if "email" in changes:
            changes["email"] = self._text(str(changes["email"]), "Email")
            if "@" not in changes["email"]:
                raise ValueError("Email must contain '@'.")
        if "role" in changes and changes["role"] not in {"member", "librarian", "admin"}:
            raise ValueError("Invalid member role.")
        for key, value in changes.items():
            setattr(member, key, value)
        self.save()
        return member

    def remove_member(self, member_id: int) -> None:
        self._require_member(member_id)
        if any(loan.member_id == member_id and loan.is_open for loan in self.loans.values()):
            raise ValueError("Cannot remove a member with active loans.")
        del self.members[member_id]
        self.save()

    def search_members(self, query: str = "") -> list[Member]:
        query = query.strip().lower()
        return [member for member in self.members.values()
                if not query or query in member.name.lower() or query in member.email.lower()]

    # Loan operations -----------------------------------------------------
    def borrow_book(self, book_id: int, member_id: int,
                    loan_days: int = DEFAULT_LOAN_DAYS,
                    borrowed_on: date | None = None) -> Loan:
        book = self._require_book(book_id)
        member = self._require_member(member_id)
        if not member.active:
            raise ValueError("Member account is inactive.")
        if book.available_copies == 0:
            raise ValueError("Book is not available.")
        loan_days = self._positive(loan_days, "Loan days")
        borrowed_on = borrowed_on or date.today()
        loan = Loan(self._next_id(self.loans), book_id, member_id,
                    borrowed_on.isoformat(),
                    (borrowed_on + timedelta(days=loan_days)).isoformat())
        book.available_copies -= 1
        self.loans[loan.loan_id] = loan
        self.save()
        return loan

    def return_book(self, book_id: int, returned_on: date | None = None) -> Loan:
        book = self._require_book(book_id)
        open_loans = [loan for loan in self.loans.values()
                      if loan.book_id == book_id and loan.is_open]
        if not open_loans:
            raise ValueError("Book is not currently borrowed.")
        loan = sorted(open_loans, key=lambda item: item.loan_id)[0]
        returned_on = returned_on or date.today()
        due_on = date.fromisoformat(loan.due_on)
        late_days = max(0, (returned_on - due_on).days)
        loan.returned_on = returned_on.isoformat()
        loan.fine = round(late_days * DAILY_FINE, 2)
        book.available_copies += 1
        self.save()
        return loan

    def renew_loan(self, loan_id: int, extra_days: int = DEFAULT_LOAN_DAYS) -> Loan:
        if loan_id not in self.loans:
            raise ValueError("Loan not found.")
        loan = self.loans[loan_id]
        if not loan.is_open:
            raise ValueError("Returned loans cannot be renewed.")
        extra_days = self._positive(extra_days, "Extra days")
        loan.due_on = (date.fromisoformat(loan.due_on) + timedelta(days=extra_days)).isoformat()
        self.save()
        return loan

    def overdue_loans(self, as_of: date | None = None) -> list[Loan]:
        as_of = as_of or date.today()
        return [loan for loan in self.loans.values()
                if loan.is_open and date.fromisoformat(loan.due_on) < as_of]

    def loans_for_member(self, member_id: int, active_only: bool = False) -> list[Loan]:
        self._require_member(member_id)
        return [loan for loan in self.loans.values()
                if loan.member_id == member_id and (not active_only or loan.is_open)]

    def loans_for_book(self, book_id: int) -> list[Loan]:
        self._require_book(book_id)
        return [loan for loan in self.loans.values() if loan.book_id == book_id]

    # Reports and exports -------------------------------------------------
    def statistics(self) -> dict[str, int | float]:
        return {
            "titles": len(self.books),
            "total_copies": sum(book.copies for book in self.books.values()),
            "available_copies": sum(book.available_copies for book in self.books.values()),
            "members": len(self.members),
            "active_loans": sum(loan.is_open for loan in self.loans.values()),
            "overdue_loans": len(self.overdue_loans()),
            "fines_collected": round(sum(loan.fine for loan in self.loans.values()), 2),
        }

    def popular_books(self, limit: int = 5) -> list[tuple[Book, int]]:
        counts = {book_id: 0 for book_id in self.books}
        for loan in self.loans.values():
            if loan.book_id in counts:
                counts[loan.book_id] += 1
        ranked = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
        return [(self.books[book_id], count) for book_id, count in ranked[:limit]]

    def export_books_csv(self, output_file: str | Path) -> Path:
        output_path = Path(output_file)
        fields = ["book_id", "title", "author", "year", "category", "copies", "available_copies"]
        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            for book in self.books.values():
                writer.writerow(asdict(book))
        return output_path

    def export_loans_csv(self, output_file: str | Path) -> Path:
        output_path = Path(output_file)
        fields = list(Loan.__dataclass_fields__)
        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            for loan in self.loans.values():
                writer.writerow(asdict(loan))
        return output_path


def display_books(library: Library, query: str = "") -> None:
    books = library.search_books(query)
    if not books:
        print("No books found.")
        return
    for book in books:
        print(f"#{book.book_id} | {book.title} | {book.author} ({book.year}) | "
              f"{book.category} | {book.available_copies}/{book.copies} available")


def display_statistics(library: Library) -> None:
    print("\nLibrary statistics")
    for key, value in library.statistics().items():
        print(f"{key.replace('_', ' ').title()}: {value}")


def run_cli() -> None:
    library = Library()
    menu = """
Library Management System
1. Add book                         9.  Update member
2. List/search books                10. Remove member
3. Register member                  11. Renew loan
4. List/search members              12. List overdue loans
5. Borrow book                      13. Show statistics
6. Return book                      14. Export CSV files
7. Update book                      15. List categories
8. Remove book                      16. Exit
"""
    while True:
        print(menu)
        choice = input("Choose an option: ").strip()
        try:
            if choice == "1":
                book = library.add_book(input("Title: "), input("Author: "), int(input("Year: ")),
                                        input("Category: ") or "General", int(input("Copies: ") or "1"))
                print(f"Added book #{book.book_id}.")
            elif choice == "2":
                display_books(library, input("Search: "))
            elif choice == "3":
                member = library.register_member(input("Name: "), input("Email: "),
                                                 input("Role [member]: ") or "member")
                print(f"Registered member #{member.member_id}.")
            elif choice == "4":
                for member in library.search_members(input("Search: ")):
                    print(f"#{member.member_id} | {member.name} | {member.email} | {member.role}")
            elif choice == "5":
                loan = library.borrow_book(int(input("Book ID: ")), int(input("Member ID: ")))
                print(f"Loan #{loan.loan_id} created; due {loan.due_on}.")
            elif choice == "6":
                loan = library.return_book(int(input("Book ID: ")))
                print(f"Book returned. Fine: ${loan.fine:.2f}")
            elif choice == "7":
                library.update_book(int(input("Book ID: ")), title=input("New title: "))
                print("Book updated.")
            elif choice == "8":
                library.remove_book(int(input("Book ID: ")))
                print("Book removed.")
            elif choice == "9":
                library.update_member(int(input("Member ID: ")), name=input("New name: "))
                print("Member updated.")
            elif choice == "10":
                library.remove_member(int(input("Member ID: ")))
                print("Member removed.")
            elif choice == "11":
                loan = library.renew_loan(int(input("Loan ID: ")), int(input("Extra days: ")))
                print(f"Loan renewed until {loan.due_on}.")
            elif choice == "12":
                for loan in library.overdue_loans():
                    print(f"Loan #{loan.loan_id}: book #{loan.book_id}, member #{loan.member_id}, due {loan.due_on}")
            elif choice == "13":
                display_statistics(library)
            elif choice == "14":
                library.export_books_csv("books.csv")
                library.export_loans_csv("loans.csv")
                print("Exported books.csv and loans.csv.")
            elif choice == "15":
                print("Categories: " + ", ".join(library.categories()))
            elif choice == "16":
                print("Goodbye!")
                break
            else:
                print("Please choose a number from 1 to 16.")
        except (ValueError, json.JSONDecodeError) as error:
            print(f"Error: {error}")


if __name__ == "__main__":
    run_cli()

