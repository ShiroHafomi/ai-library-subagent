"""LangChain SQL Toolkit cho tra cứu sách (tài khoản MySQL chỉ đọc).

Toolkit có thể thực thi SQL do model sinh; MySQL chỉ cấp SELECT cho tài khoản này
trên bảng books. Metadata cục bộ chỉ phục vụ phản chiếu schema đáng tin cậy.
"""
import os
from sqlalchemy import Column, MetaData, Table, create_engine, inspect
from sqlalchemy.engine import URL
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit


def create_book_sql_tools(model):
    """Tạo SQL tools chỉ truy cập bảng books bằng tài khoản SELECT-only."""
    user = os.getenv('DB_READONLY_USER')
    password = os.getenv('DB_READONLY_PASSWORD')
    if not user or not password:
        raise RuntimeError('Thiếu DB_READONLY_USER/DB_READONLY_PASSWORD (tài khoản chỉ có quyền SELECT).')
    url = URL.create(
        'mysql+pymysql', username=user, password=password,
        host=os.getenv('DB_HOST', 'localhost'),
        port=int(os.getenv('DB_PORT', '3306')),
        database=os.getenv('DB_NAME'),
    )
    engine = create_engine(url)
    inspector = inspect(engine)
    primary_keys = set(
        inspector.get_pk_constraint('books')['constrained_columns'] or []
    )
    # Keep column metadata only; following foreign keys can require access to other tables.
    columns = [
        Column(
            column['name'],
            column['type'],
            nullable=column['nullable'],
            primary_key=column['name'] in primary_keys,
        )
        for column in inspector.get_columns('books')
    ]
    metadata = MetaData()
    Table('books', metadata, *columns)
    db = SQLDatabase(
        engine,
        metadata=metadata,
        include_tables=['books'],
        sample_rows_in_table_info=0,
        lazy_table_reflection=True,
    )
    return SQLDatabaseToolkit(db=db, llm=model).get_tools()
