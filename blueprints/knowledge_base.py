import chromadb
import uuid
import requests
from blueprints.config import OLLAMA_HOST, EMBEDDING_MODEL_NAME

chroma_client = chromadb.PersistentClient(path="./user/knowledge_db")
collection = chroma_client.get_or_create_collection(name="document_knowledge")

def get_embedding(text):
    try:
        res = requests.post(f"{OLLAMA_HOST}/api/embeddings", json={"model": EMBEDDING_MODEL_NAME, "prompt": text})
        return res.json().get("embedding", [])
    except Exception as e:
        print(f"Embedding Error: {e}")
        return []

def add_document_to_db(text, filename):
    chunks = [text[i:i+1000] for i in range(0, len(text), 1000)]
    for chunk in chunks:
        emb = get_embedding(chunk)
        if emb:
            collection.add(
                embeddings=[emb], 
                documents=[chunk], 
                metadatas=[{"source": filename}], 
                ids=[str(uuid.uuid4())]
            )

def search_knowledge_base(query, n_results=3):
    emb = get_embedding(query)
    if not emb:
        return ""
    results = collection.query(query_embeddings=[emb], n_results=n_results)
    if results and results.get('documents') and results['documents'][0]:
        return "\n\n".join(results['documents'][0])
    return ""

def get_all_sources():
    results = collection.get(include=['metadatas'])
    sources = set()
    for meta in results.get('metadatas', []):
        if meta and 'source' in meta:
            sources.add(meta['source'])
    return list(sources)

def delete_document_by_source(source):
    collection.delete(where={"source": source})

def get_document_content(source):
    results = collection.get(where={"source": source}, include=['documents'])
    docs = results.get('documents', [])
    return "\n\n--- Chunk Separator ---\n\n".join(docs)