from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from app.config import DATA_PATH, FAISS_INDEX_PATH


def build_faiss_index():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        raw_text = f.read()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=350,
        chunk_overlap=50,
        separators=["\n\n", "\n", " "]
    )
    chunks = splitter.create_documents([raw_text])

    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vector_store = FAISS.from_documents(chunks, embeddings)
    vector_store.save_local(FAISS_INDEX_PATH)
    print(f"FAISS index built successfully with {len(chunks)} chunks at {FAISS_INDEX_PATH}")


def retrieve_first_aid_context(query: str, k: int = 2) -> str:
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vector_store = FAISS.load_local(
        FAISS_INDEX_PATH,
        embeddings,
        allow_dangerous_deserialization=True
    )
    docs = vector_store.similarity_search(query, k=k)
    return "\n".join([doc.page_content for doc in docs])


if __name__ == "__main__":
    build_faiss_index()