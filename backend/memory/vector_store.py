"""
vector_store.py - Kết nối LlamaIndex với PostgreSQL (pgvector)
Quản lý Vector Store để lưu trữ và truy xuất embedding

LƯU Ý: LlamaIndex mặc định dùng OpenAI làm LLM cho query_engine.
Ta override bằng cách dùng VectorStoreIndex.as_retriever() thay vì as_query_engine()
để tránh cần OpenAI API key.
"""

from llama_index.core import VectorStoreIndex, StorageContext, Document, Settings
from llama_index.vector_stores.postgres import PGVectorStore
from llama_index.embeddings.google import GeminiEmbedding
from sqlalchemy import make_url
from typing import Optional
from config import get_settings


class VectorStoreManager:
    """
    Quản lý kết nối tới pgvector thông qua LlamaIndex.
    
    Dùng Retriever (không dùng query_engine) để tránh dependency vào OpenAI.
    """

    def __init__(self, collection_name: Optional[str] = None):
        self.settings = get_settings()
        self.collection_name = collection_name or self.settings.collection_name

        # === Setup Embedding Model (Google) ===
        self._embed_model = GeminiEmbedding(
            model_name="models/gemini-embedding-001",
        )

        # === Override global LlamaIndex settings để không dùng OpenAI ===
        Settings.embed_model = self._embed_model
        Settings.llm = None  # Tắt LLM mặc định (OpenAI)

        # === Setup PGVector Store ===
        url = make_url(self.settings.database_url)
        self._vector_store = PGVectorStore.from_params(
            database=url.database,
            host=url.host,
            password=url.password,
            port=str(url.port),
            user=url.username,
            table_name=self.collection_name,
            embed_dim=self.settings.embedding_dimension,
        )

        # === Storage Context ===
        self._storage_context = StorageContext.from_defaults(
            vector_store=self._vector_store
        )

        # === Index (lazy init) ===
        self._index: Optional[VectorStoreIndex] = None

    def get_index(self) -> VectorStoreIndex:
        """Lấy hoặc tạo VectorStoreIndex"""
        if self._index is None:
            self._index = VectorStoreIndex.from_vector_store(
                vector_store=self._vector_store,
                embed_model=self._embed_model,
            )
        return self._index

    def add_documents(self, texts: list[str], metadata_list: Optional[list[dict]] = None):
        """
        Thêm documents vào vector store.
        """
        documents = []
        for i, text in enumerate(texts):
            meta = metadata_list[i] if metadata_list and i < len(metadata_list) else {}
            documents.append(Document(text=text, metadata=meta))

        self._index = VectorStoreIndex.from_documents(
            documents,
            storage_context=self._storage_context,
            embed_model=self._embed_model,
        )

    def query(self, query_text: str, top_k: int = 3) -> str:
        """
        Tìm kiếm thông tin liên quan trong vector store.
        Dùng Retriever (similarity search) thay vì query_engine để không cần OpenAI.
        
        Returns:
            Chuỗi text kết quả tìm được (nối các node text lại)
        """
        index = self.get_index()
        retriever = index.as_retriever(
            similarity_top_k=top_k,
        )
        nodes = retriever.retrieve(query_text)

        if not nodes:
            return "Empty Response"

        # Nối text từ các nodes tìm được
        results = []
        for node in nodes:
            results.append(node.get_content())

        return "\n---\n".join(results)


# === Singleton instances ===
_user_memory_store: Optional[VectorStoreManager] = None
_news_store: Optional[VectorStoreManager] = None


def get_user_memory_store() -> VectorStoreManager:
    """Lấy singleton VectorStoreManager cho user memory"""
    global _user_memory_store
    if _user_memory_store is None:
        _user_memory_store = VectorStoreManager(collection_name="aia_user_memory")
    return _user_memory_store


def get_news_store() -> VectorStoreManager:
    """Lấy singleton VectorStoreManager cho news articles"""
    global _news_store
    if _news_store is None:
        _news_store = VectorStoreManager(collection_name="aia_news_articles")
    return _news_store
