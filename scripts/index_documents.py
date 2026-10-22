from rag.store import index_policy

if __name__ == '__main__':
    print('Đã cập nhật chỉ mục RAG.' if index_policy() else 'Chỉ mục RAG đã mới nhất.')
