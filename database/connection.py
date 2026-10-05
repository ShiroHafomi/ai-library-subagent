import os

import mysql.connector
from dotenv import load_dotenv
from mysql.connector import Error

from config import ENV_FILE

load_dotenv(ENV_FILE)


def get_connection():
    try:
        return mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "3306")),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
        )
    except Error as exc:
        raise RuntimeError(f"Không thể kết nối tới MySQL: {exc}") from exc
