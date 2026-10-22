-- Additive schema for authenticated library borrowing. Apply only after review.
-- Existing books and user_memories tables are intentionally untouched.

CREATE TABLE IF NOT EXISTS members (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_members_status (status)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS borrow_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    member_id INT NOT NULL,
    book_id INT NOT NULL,
    borrowed_at DATETIME NOT NULL,
    due_at DATETIME NOT NULL,
    returned_at DATETIME NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'borrowed',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_borrow_member_status (member_id, status),
    INDEX idx_borrow_book_status (book_id, status),
    CONSTRAINT fk_borrow_records_member
        FOREIGN KEY (member_id) REFERENCES members (id),
    CONSTRAINT fk_borrow_records_book
        FOREIGN KEY (book_id) REFERENCES books (id)
) ENGINE=InnoDB;
