from database.connection import get_connection


def initialize_database() -> None:
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS books (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                author VARCHAR(255) NOT NULL,
                category VARCHAR(255) NOT NULL,
                is_available BOOLEAN NOT NULL DEFAULT TRUE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_memories (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id VARCHAR(255) NOT NULL,
                memory_key VARCHAR(255) NOT NULL,
                memory_value TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY unique_user_memory (user_id, memory_key)
            )
            """
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()
