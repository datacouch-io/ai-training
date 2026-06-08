import os
from dotenv import load_dotenv
from openai import OpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
)

load_dotenv()

# ==========================================
# 1. Configuration & Client Setup
# ==========================================
def get_base_url(raw_endpoint: str) -> str:
    base = raw_endpoint.rstrip("/")
    if "/api/projects/" in base:
        return f"{base.split('/api/projects/')[0]}/openai/v1"
    if base.endswith("/models"):
        return base.rsplit("/models", 1)[0] + "/openai/v1"
    if not base.endswith("/openai/v1"):
        return f"{base}/openai/v1"
    return base

# OpenAI Client for Embeddings
oai_client = OpenAI(
    api_key=os.getenv("FOUNDRY_API_KEY"),
    base_url=get_base_url(os.getenv("FOUNDRY_ENDPOINT", ""))
)
EMBEDDING_MODEL = "text-embedding-3-small"

# Azure AI Search Clients
search_endpoint = os.getenv("SEARCH_ENDPOINT")
search_credential = AzureKeyCredential(os.getenv("SEARCH_ADMIN_KEY"))
INDEX_NAME = "employee-handbook-index"

index_client = SearchIndexClient(endpoint=search_endpoint, credential=search_credential)
search_client = SearchClient(endpoint=search_endpoint, index_name=INDEX_NAME, credential=search_credential)

# ==========================================
# 2. Define the Vector Database Schema
# ==========================================
def create_index():
    print(f"Creating or updating index '{INDEX_NAME}'...")
    
    # Define the fields of our database
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SearchField(
            name="content_vector", 
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True, 
            vector_search_dimensions=1536, # Standard dimension for text-embedding-3-small
            vector_search_profile_name="myHnswProfile"
        )
    ]

    # Configure the Vector Search Algorithm (HNSW is standard for fast approximate nearest neighbors)
    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="myHnsw")],
        profiles=[VectorSearchProfile(name="myHnswProfile", algorithm_configuration_name="myHnsw")]
    )

    index = SearchIndex(name=INDEX_NAME, fields=fields, vector_search=vector_search)
    index_client.create_or_update_index(index)
    print("Index created successfully.\n")

# ==========================================
# 3. Generate Embeddings and Upsert
# ==========================================
def generate_embedding(text: str) -> list[float]:
    """Calls Azure OpenAI to convert text into a 1536-dimension float array."""
    response = oai_client.embeddings.create(input=text, model=EMBEDDING_MODEL)
    return response.data[0].embedding

def ingest_documents():
    # Mock raw documents (In a real app, these are read from PDFs or Databases)
    documents = [
        {"id": "doc1", "content": "Contoso Electronics Work From Home Policy: Employees may work from home up to 3 days a week. Core hours are 10 AM to 3 PM."},
        {"id": "doc2", "content": "Contoso Expense Policy: Meals during corporate travel can be expensed up to $75 per day. Alcohol is strictly non-reimbursable."},
        {"id": "doc3", "content": "IT Security Guidelines: Passwords must be 16 characters long and changed every 90 days. Never share credentials over Slack."}
    ]

    print("Generating embeddings for documents...")
    docs_to_upload = []
    
    for doc in documents:
        print(f"  Embedding -> {doc['id']}")
        # 1. Generate the vector
        vector = generate_embedding(doc["content"])
        
        # 2. Package the text and the vector together
        docs_to_upload.append({
            "id": doc["id"],
            "content": doc["content"],
            "content_vector": vector
        })

    # 3. Upload to Azure AI Search
    print("\nUploading documents to Azure AI Search...")
    result = search_client.upload_documents(documents=docs_to_upload)
    print(f"Successfully uploaded {len(result)} documents to the vector store!")

if __name__ == "__main__":
    create_index()
    ingest_documents()
