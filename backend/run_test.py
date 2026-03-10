import asyncio
import uuid
from app.api.v1.kb import _process_document_background

async def main():
    try:
        await _process_document_background(
            document_id=str(uuid.uuid4()),
            collection_id=str(uuid.uuid4()),
            qdrant_collection_name="test_collection",
            file_path="test.txt",
            mime_type="text/plain",
            doc_title="Test Title",
            doc_category="Test Category",
            sensitivity="confidential",
        )
        print("Success!")
    except Exception as e:
        print(f"Exception caught: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
