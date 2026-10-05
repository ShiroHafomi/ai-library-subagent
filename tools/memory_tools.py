from langchain.tools import tool

from config import get_memory_user_id
from database.connection import get_connection


@tool
def read_memory(query: str) -> str:
    """Search for memories matching the query in memory value for the current user."""
    # If query is empty, return a message asking for a query? We'll return empty string or message.
    # However, the problem does not specify behavior for empty query. We'll allow empty query to return all?
    # But note: using LIKE with empty string and wildcards would match everything.
    # We'll decide to return a message if query is empty after stripping.
    query = query.strip()
    if not query:
        return "Please provide a non-empty query to search memories."

    user_id = get_memory_user_id()
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        # Search in memory_value with LIKE, using wildcards
        sql = """
            SELECT memory_key, memory_value
            FROM user_memories
            WHERE user_id = %s AND memory_value LIKE %s
        """
        # Use %s for parameter and add wildcards in the parameter value
        search_term = f"%{query}%"
        cursor.execute(sql, (user_id, search_term))
        rows = cursor.fetchall()
    finally:
        cursor.close()
        connection.close()

    if not rows:
        return f"No memories found matching '{query}'."

    # Format the results as a string
    results = []
    for row in rows:
        results.append(f"Key: {row['memory_key']}\nValue: {row['memory_value']}")
    return "\n\n---\n\n".join(results)


@tool
def save_memory(memory_key: str, memory_value: str) -> str:
    """Save a memory with the given key and value for the current user, using upsert."""
    memory_key = memory_key.strip()
    memory_value = memory_value.strip()
    if not memory_key:
        return "Memory key cannot be empty."
    if not memory_value:
        return "Memory value cannot be empty."

    user_id = get_memory_user_id()
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        # Insert or update on duplicate key (user_id, memory_key)
        sql = """
            INSERT INTO user_memories (user_id, memory_key, memory_value)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                memory_value = VALUES(memory_value),
                updated_at = CURRENT_TIMESTAMP
        """
        cursor.execute(sql, (user_id, memory_key, memory_value))
        connection.commit()
    finally:
        cursor.close()
        connection.close()

    return f"Memory saved with key '{memory_key}'."