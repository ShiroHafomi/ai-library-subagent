import hashlib
import json
import os
from pathlib import Path

from config import BASE_DIR, POLICY_FILE, get_api_key

INDEX_DIR = BASE_DIR / 'data' / 'chroma_policy'
MANIFEST = INDEX_DIR / 'manifest.json'


def _components():
    from langchain_chroma import Chroma
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    embeddings = GoogleGenerativeAIEmbeddings(
        model=os.getenv('GEMINI_EMBEDDING_MODEL', 'models/gemini-embedding-001'),
        google_api_key=get_api_key(),
    )
    return Chroma, embeddings, RecursiveCharacterTextSplitter


def _documents():
    from langchain_core.documents import Document
    if not POLICY_FILE.exists():
        return []
    content = POLICY_FILE.read_text(encoding='utf-8').strip()
    if not content:
        return []
    return [Document(page_content=content, metadata={'source': POLICY_FILE.name, 'is_demo': 'DEMO' in content[:250]})]


def index_policy(force=False):
    docs = _documents()
    if not docs:
        raise ValueError('Không có tài liệu nội quy để lập chỉ mục.')
    digest = hashlib.sha256(docs[0].page_content.encode('utf-8')).hexdigest()
    Chroma, embeddings, Splitter = _components()
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    if not force and MANIFEST.exists():
        try:
            if json.loads(MANIFEST.read_text(encoding='utf-8')).get('sha256') == digest:
                return False
        except (ValueError, OSError):
            pass
    splitter = Splitter(chunk_size=650, chunk_overlap=100, add_start_index=True)
    chunks = splitter.split_documents(docs)
    # Tạo collection mới theo hash; chỉ đổi manifest khi indexing thành công.
    collection = 'policy_' + digest[:24]
    store = Chroma(collection_name=collection, embedding_function=embeddings, persist_directory=str(INDEX_DIR))
    store.add_documents(chunks, ids=[f'{digest}-{i}' for i in range(len(chunks))])
    MANIFEST.write_text(json.dumps({'sha256': digest, 'collection': collection}, ensure_ascii=False), encoding='utf-8')
    return True


def retrieve_policy(question, k=4):
    if not question.strip():
        return []
    if not MANIFEST.exists():
        raise RuntimeError('Chưa có chỉ mục RAG. Chạy: python -m scripts.index_documents')
    info = json.loads(MANIFEST.read_text(encoding='utf-8'))
    docs = _documents()
    if not docs or hashlib.sha256(docs[0].page_content.encode('utf-8')).hexdigest() != info['sha256']:
        raise RuntimeError('Tài liệu nội quy đã thay đổi. Hãy chạy lại indexing.')
    Chroma, embeddings, _ = _components()
    store = Chroma(collection_name=info['collection'], embedding_function=embeddings, persist_directory=str(INDEX_DIR))
    # Chỉ cung cấp các đoạn có khoảng cách đủ gần; tránh suy diễn khi không có căn cứ.
    results = store.similarity_search_with_relevance_scores(question, k=k)
    threshold = float(os.getenv('RAG_MIN_RELEVANCE', '0.35'))
    return [(doc, score) for doc, score in results if score >= threshold]
