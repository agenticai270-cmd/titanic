import java.util.ArrayList;
import java.util.List;
import java.util.Scanner;
import java.io.IOException;
import java.io.ObjectInputStream;
import java.io.ObjectOutputStream;
import java.io.Se
/** A simple command-line library management system in Java. */
public class LibraryManager {
    private statifinal List<Member> members = new ArrayList<>();

    private static class Book implements Serializable {
        private static final long serialVersionUID = 1L;
        int id;
        Book(int id, String title, String author, int year) {
            this.id = id;
            this.title = title;
            this.author = author;
            this.year = year;
        }
    }

    private static class Member implements Serializable {
        private static final long serialVersionUID = 1L;
        int id;
        String name;
        String email;

        Member(int id, String name, String email) {
            this.id = id;
            this.name = name;
            this.email = email;
        }
    }

    public static void main(String[] args) {
        loadData();
        while (true) {
            printMenu();
            String choice = scanner.nextLine().trim();
            try {
                switch (choice) {
                    case "1" -> addBook();
                    case "2" -> listBooks();
                    case "3" -> registerMember();
                    case "4" -> listMembers();
                    case "5" -> borrowBook();
                    case "6" -> returnBook();
                    case "7" -> {
                        System.out.println("Goodbye!");
                        return;
                    }
                    default -> System.out.println("Please choose a number from 1 to 7.");
                }
            } catch (IllegalArgumentException error) {
                System.out.println("Error: " + error.getMessage());
            } catch (IllegalStateException error) {
                System.out.println("Storage error: " + error.getMessage());
            }
        }
    }

    private static void printMenu() {
        System.out.println("\nLibrary Management System (Java)");
        System.out.println("1. Add book");
        System.out.println("2. List/search books");
        System.out.println("3. Register member");
        System.out.println("4. List members");
        System.out.println("5. Borrow book");
        System.out.println("6. Return book");
        System.out.println("7. Exit");
        System.out.print("Choose an option: ");
    }

    private static void addBook() {
        String title = ask("Title: ");
        String author = ask("Author: ");
        int year = Integer.parseInt(ask("Publication year: "));
        if (title.isBlank() || author.isBlank() || year < 0) {
            throw new IllegalArgumentException("Enter a valid title, author, and year.");
        }
        Book book = new Book(books.size() + 1, title, author, year);
        books.add(book);
        saveData();
        System.out.println("Added book #" + book.id + ".");
    }

    private static void listBooks() {
        String query = ask("Search (leave blank for all): ").toLowerCase();
        boolean found = false;
        for (Book book : books) {
            if (query.isBlank()
                    || book.title.toLowerCase().contains(query)
                    || book.author.toLowerCase().contains(query)) {
                String status = book.borrowedBy == null
                        ? "Available"
                        : "Borrowed by member #" + book.borrowedBy;
                System.out.printf("#%d | %s | %s (%d) | %s%n",
                        book.id, book.title, book.author, book.year, status);
                found = true;
            }
        }
        if (!found) {
            System.out.println("No books found.");
        }
    }

    private static void registerMember() {
        String name = ask("Name: ");
        String email = ask("Email: ");
        if (name.isBlank() || email.isBlank()) {
            throw new IllegalArgumentException("Name and email are required.");
        }
        Member member = new Member(members.size() + 1, name, email);
        members.add(member);
        saveData();
        System.out.println("Registered member #" + member.id + ".");
    }

    private static void listMembers() {
        if (members.isEmpty()) {
            System.out.println("No members found.");
            return;
        }
        for (Member member : members) {
            System.out.printf("#%d | %s | %s%n", member.id, member.name, member.email);
        }
    }

    private static void borrowBook() {
        Book book = findBook(Integer.parseInt(ask("Book ID: ")));
        int memberId = Integer.parseInt(ask("Member ID: "));
        findMember(memberId);
        if (book.borrowedBy != null) {
            throw new IllegalArgumentException("Book is already borrowed.");
        }
        book.borrowedBy = memberId;
        saveData();
        System.out.println("Book borrowed successfully.");
    }

    private static void returnBook() {
        Book book = findBook(Integer.parseInt(ask("Book ID: ")));
        if (book.borrowedBy == null) {
            throw new IllegalArgumentException("Book is not currently borrowed.");
        }
        book.borrowedBy = null;
        saveData();
        System.out.println("Book returned successfully.");
    }

    private static void loadData() {
        if (!Files.exists(DATA_FILE)) {
            return;
        }
        try (ObjectInputStream input = new ObjectInputStream(Files.newInputStream(DATA_FILE))) {
            @SuppressWarnings("unchecked")
            List<Book> savedBooks = (List<Book>) input.readObject();
            @SuppressWarnings("unchecked")
            List<Member> savedMembers = (List<Member>) input.readObject();
            books.addAll(savedBooks);
            members.addAll(savedMembers);
        } catch (IOException | ClassNotFoundException | ClassCastException error) {
            System.out.println("Could not load saved data: " + error.getMessage());
        }
    }

    private static void saveData() {
        try (ObjectOutputStream output = new ObjectOutputStream(Files.newOutputStream(DATA_FILE))) {
            output.writeObject(books);
            output.writeObject(members);
        } catch (IOException error) {
            throw new IllegalStateException("Could not save data to " + DATA_FILE, error);
        }
    }

    private static Book findBook(int id) {
        return books.stream()
                .filter(book -> book.id == id)
                .findFirst()
                .orElseThrow(() -> new IllegalArgumentException("Book not found."));
    }

    private static void findMember(int id) {
        boolean exists = members.stream().anyMatch(member -> member.id == id);
        if (!exists) {
            throw new IllegalArgumentException("Member not found.");
        }
    }

    private static String ask(String prompt) {
        System.out.print(prompt);
        return scanner.nextLine().trim();
    }
}
