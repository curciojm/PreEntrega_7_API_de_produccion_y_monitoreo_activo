import os

from langchain_huggingface import HuggingFaceEmbeddings

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

INDEX_NAME = os.getenv("INDEX_NAME")

NAMESPACE = "Statistics_and_methodolgy_texts"

EMBEDDINGS = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

DIMENSIONS = 384