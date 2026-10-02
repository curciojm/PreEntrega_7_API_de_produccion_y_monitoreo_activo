from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader
from langchain_core.documents import Document

from chunking import DocumentProcessor
from db_config import NAMESPACE


def procesamiento_desde_pdfs():
    print("📄 Pinecone vacío. Procesando PDFs...")

    loader = DirectoryLoader(
        "data",
        glob="*.pdf",
        loader_cls=PyPDFLoader
    )

    documentos_crudos = loader.load()

    processor = DocumentProcessor()

    return processor.process_document(documentos_crudos)

def recuperar_documentos_de_pinecone(index):
    print("📦 Recuperando documentos desde Pinecone...")

    ids = []

    for pagina in index.list(namespace=NAMESPACE):
        ids.extend(pagina)

    documentos = []

    batch_size = 100

    for i in range(0, len(ids), batch_size):
        batch_ids = ids[i:i + batch_size]

        registros = index.fetch(
            ids=batch_ids,
            namespace=NAMESPACE
        )

        for vector in registros.vectors.values():
            metadata = vector.metadata

            documentos.append(
                Document(
                    page_content=metadata["text"],
                    metadata=metadata
                )
            )

    print(f"📄 Documentos recuperados: {len(documentos)}")

    return documentos