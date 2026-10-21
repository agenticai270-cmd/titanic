# titanic reviewer notes

## Architecture

This is a beginner-friendly library-management application with two implementations: the primary dependency-free Python CLI/domain layer and a smaller standalone Java CLI (`library_management/LibraryManager.java`). Python models books, members, and loans in `library_manager.py`, persists JSON atomically, and keeps reservation/waitlist logic in the UI-independent `reservations.py`. Standard-library `unittest` suites cover both domains using temporary data files.

## Conventions

- Python domain operations validate inputs, mutate in-memory state, call `save()`, and return the affected object; see `Library.add_book`, `borrow_book`, and `ReservationManager.place_reservation`.
- Missing entities and invalid state transitions raise `ValueError` with user-facing messages, using helpers such as `_require_book`, `_require_member`, and `ReservationManager._require`.
- IDs are integer, 1-based, and generated as `max(existing_ids, default=0) + 1`; reservation audit-list IDs use `len(items) + 1` (`library_manager.py`, `reservations.py`).
- Persist dataclasses with `dataclasses.asdict`; JSON files include a `version` field. Writes use a sibling `.tmp` file followed by `replace()` for atomic replacement (`Library.save`, `ReservationManager.save`).
- Dates are stored as ISO strings and converted with `date.fromisoformat`; injectable dates such as `borrowed_on`, `created_on`, and `as_of` support deterministic behavior in tests.
- Reservation lifecycle is represented by explicit states (`waiting`, `ready`, `fulfilled`, `cancelled`, `expired`), with FIFO ordering by `(created_on, reservation_id)` and an audit entry for lifecycle actions (`reservations.py`).
- Tests use `unittest`, `TemporaryDirectory`, and `Path`; persistence and error behavior are commonly asserted directly against loaded objects or `assertRaisesRegex` (`test_library_manager.py`, `test_reservations.py`).
- The Java implementation is intentionally independent: static in-memory `ArrayList`s, nested `Serializable` entities, binary persistence in `library_data_java.bin`, and a small menu-based feature set.

## Intentional non-standard choices

- The Python and Java applications do not share data formats or feature parity. Python uses `library_data.json`; Java uses Java serialization in `library_data_java.bin`.
- Python automatically saves after successful mutations and migrates legacy books containing `borrowed_by` into open `Loan` records (`Library._migrate_legacy_loans`).
- Returning a book accepts only a `book_id` and selects the oldest open loan by `loan_id`; this supports multiple copies without requiring a loan ID (`Library.return_book`).
- Reservations are deliberately decoupled from `Library` and the CLI so other interfaces can reuse their rules (`reservations.py` module docstring).

## Watch out for

- Preserve inventory invariants: `available_copies` must remain between zero and `copies`; updates must not reduce total copies below currently borrowed copies (`Library.update_book`, `borrow_book`, `return_book`).
- Do not bypass `save()` after state changes; persistence is part of the public behavior and is tested.
- Keep reservation transitions FIFO and auditable. In particular, `mark_ready` must not skip an earlier waiting reservation or silently omit an audit record.
- Be careful with date semantics: `Reservation.is_expired` uses `date.today()`, while `expire_reservations` accepts `as_of`; changes should avoid mixing those clocks.
- Maintain legacy-load compatibility for records with missing `category`/copy fields and legacy `borrowed_by` values (`Library._book_from_dict`, `_migrate_legacy_loans`).
- Treat changes to Java serialization classes or `serialVersionUID` as persistence-format changes; Java data is not JSON-compatible with the Python implementation.