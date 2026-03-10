"""ExecMind - Qdrant vector indexer for document chunk storage."""

import uuid as uuid_module

from app.core.config import settings
from app.utils.logging import get_logger

logger = get_logger("indexer")


class QdrantIndexer:
    """Manages Qdrant collections and vector upsert operations."""

    def __init__(self, qdrant_client=None):
        self.client = qdrant_client

    def ensure_collection(self, collection_name: str) -> None:
        """Create a Qdrant collection if it doesn't exist.

        Args:
            collection_name: Name of the Qdrant collection.
        """
        if self.client is None:
            logger.warning("qdrant_client_not_configured")
            return

        from qdrant_client.models import Distance, VectorParams

        existing = [c.name for c in self.client.get_collections().collections]
        if collection_name not in existing:
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=settings.QDRANT_VECTOR_SIZE,
                    distance=Distance.COSINE,
                ),
            )
            logger.info("qdrant_collection_created", name=collection_name)

    def upsert_points(
        self,
        collection_name: str,
        points: list[dict],
    ) -> int:
        """Batch upsert vector points into a Qdrant collection.

        Args:
            collection_name: Target Qdrant collection name.
            points: List of dicts with 'vector' and 'payload' keys.

        Returns:
            Number of points upserted.
        """
        if self.client is None:
            logger.warning("qdrant_client_not_configured")
            return 0

        from qdrant_client.models import PointStruct

        qdrant_points = [
            PointStruct(
                id=str(uuid_module.uuid4()),
                vector=point["vector"],
                payload=point["payload"],
            )
            for point in points
        ]

        batch_size = 100
        total_upserted = 0

        for i in range(0, len(qdrant_points), batch_size):
            batch = qdrant_points[i : i + batch_size]
            self.client.upsert(
                collection_name=collection_name,
                points=batch,
            )
            total_upserted += len(batch)

        logger.info(
            "points_upserted",
            collection=collection_name,
            count=total_upserted,
        )
        return total_upserted

    def delete_by_document(
        self,
        collection_name: str,
        document_id: str,
    ) -> None:
        """Delete all points belonging to a specific document.

        Args:
            collection_name: Qdrant collection name.
            document_id: Document UUID to delete points for.
        """
        if self.client is None:
            return

        from qdrant_client.models import Filter, FieldCondition, MatchValue

        self.client.delete(
            collection_name=collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=document_id),
                    )
                ]
            ),
        )
        logger.info(
            "document_points_deleted",
            collection=collection_name,
            document_id=document_id,
        )

    def delete_collection(self, collection_name: str) -> None:
        """Delete an entire Qdrant collection.

        Args:
            collection_name: Name of the collection to delete.
        """
        if self.client is None:
            return

        self.client.delete_collection(collection_name=collection_name)
        logger.info("qdrant_collection_deleted", name=collection_name)
