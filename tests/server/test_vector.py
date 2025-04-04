import pytest
import sys
from unittest.mock import patch, MagicMock
import httpx
from opentelemetry import trace

sys.modules['openlit'] = MagicMock()

from agentuity.server.vector import VectorStore, VectorSearchResult  # noqa: E402


class TestVectorSearchResult:
    """Test suite for the VectorSearchResult class."""
    
    def test_init(self):
        """Test initialization of VectorSearchResult."""
        result = VectorSearchResult(
            id="test_id",
            key="test_key",
            distance=0.75,
            metadata={"source": "test_source"}
        )
        
        assert result.id == "test_id"
        assert result.key == "test_key"
        assert result.distance == 0.75
        assert result.metadata == {"source": "test_source"}
    
    def test_init_without_metadata(self):
        """Test initialization of VectorSearchResult without metadata."""
        result = VectorSearchResult(
            id="test_id",
            key="test_key",
            distance=0.75
        )
        
        assert result.id == "test_id"
        assert result.key == "test_key"
        assert result.distance == 0.75
        assert result.metadata is None


class TestVectorStore:
    """Test suite for the VectorStore class."""
    
    @pytest.fixture
    def mock_tracer(self):
        """Create a mock tracer for testing."""
        tracer = MagicMock(spec=trace.Tracer)
        span = MagicMock()
        tracer.start_as_current_span.return_value.__enter__.return_value = span
        return tracer
    
    @pytest.fixture
    def vector_store(self, mock_tracer):
        """Create a VectorStore instance for testing."""
        return VectorStore(
            base_url="https://api.example.com",
            api_key="test_api_key",
            tracer=mock_tracer
        )
    
    @pytest.mark.asyncio
    async def test_upsert_success(self, vector_store, mock_tracer):
        """Test successful upserting of vectors."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "data": [
                {"id": "doc1_id"},
                {"id": "doc2_id"}
            ]
        }
        
        documents = [
            {
                "key": "doc1",
                "document": "This is document 1"
            },
            {
                "key": "doc2",
                "document": "This is document 2"
            }
        ]
        
        with patch("httpx.put", return_value=mock_response):
            result = await vector_store.upsert("test_collection", documents)
            
            assert result == ["doc1_id", "doc2_id"]
            
            httpx.put.assert_called_once()
            args, kwargs = httpx.put.call_args
            
            assert args[0] == "https://api.example.com/vector/test_collection"
            assert kwargs["headers"]["Authorization"] == "Bearer test_api_key"
            assert kwargs["json"] == documents
            
            span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
            span.set_attribute.assert_called_with("name", "test_collection")
            span.add_event.assert_called_once()
            span.set_status.assert_called_once_with(trace.StatusCode.OK)
    
    @pytest.mark.asyncio
    async def test_upsert_missing_key(self, vector_store):
        """Test upserting documents with missing key."""
        documents = [
            {
                "document": "This is document 1"
            }
        ]
        
        with pytest.raises(ValueError, match="document must have a key"):
            await vector_store.upsert("test_collection", documents)
    
    @pytest.mark.asyncio
    async def test_upsert_missing_document_and_embeddings(self, vector_store):
        """Test upserting documents with missing document and embeddings."""
        documents = [
            {
                "key": "doc1"
            }
        ]
        
        with pytest.raises(ValueError, match="document must have either a document or embeddings"):
            await vector_store.upsert("test_collection", documents)
    
    @pytest.mark.asyncio
    async def test_upsert_error(self, vector_store, mock_tracer):
        """Test error handling during upsert operation."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        
        documents = [
            {
                "key": "doc1",
                "document": "This is document 1"
            }
        ]
        
        with patch("httpx.put", return_value=mock_response), \
             pytest.raises(Exception, match="Failed to upsert documents: 500"):
            await vector_store.upsert("test_collection", documents)
            
            span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
            span.set_status.assert_called_once_with(
                trace.StatusCode.ERROR, 
                "Failed to upsert documents"
            )
    
    @pytest.mark.asyncio
    async def test_get_success(self, vector_store, mock_tracer):
        """Test successful retrieval of vectors."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "data": [
                {
                    "id": "doc1_id",
                    "key": "doc1",
                    "distance": 0.75,
                    "metadata": {"source": "test"}
                }
            ]
        }
        
        with patch("httpx.get", return_value=mock_response):
            results = await vector_store.get("test_collection", "doc1")
            
            assert len(results) == 1
            assert isinstance(results[0], VectorSearchResult)
            assert results[0].id == "doc1_id"
            assert results[0].key == "doc1"
            assert results[0].distance == 0.75
            assert results[0].metadata == {"source": "test"}
            
            httpx.get.assert_called_once()
            args, kwargs = httpx.get.call_args
            
            assert args[0] == "https://api.example.com/vector/test_collection/doc1"
            assert kwargs["headers"]["Authorization"] == "Bearer test_api_key"
            
            span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
            span.set_attribute.assert_any_call("name", "test_collection")
            span.set_attribute.assert_any_call("key", "doc1")
            span.add_event.assert_called_once_with("hit")
            span.set_status.assert_called_once_with(trace.StatusCode.OK)
    
    @pytest.mark.asyncio
    async def test_get_not_found(self, vector_store, mock_tracer):
        """Test retrieval of non-existent vectors."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404
        
        with patch("httpx.get", return_value=mock_response):
            results = await vector_store.get("test_collection", "non_existent")
            
            assert len(results) == 0
            
            span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
            span.add_event.assert_called_once_with("miss")
            span.set_status.assert_called_once_with(trace.StatusCode.OK)
    
    @pytest.mark.asyncio
    async def test_get_error(self, vector_store, mock_tracer):
        """Test error handling during get operation."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        
        with patch("httpx.get", return_value=mock_response), \
             pytest.raises(Exception, match="Failed to get documents: 500"):
            await vector_store.get("test_collection", "doc1")
            
            span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
            span.set_status.assert_called_once_with(
                trace.StatusCode.ERROR, 
                "Failed to get documents"
            )
    
    @pytest.mark.asyncio
    async def test_search_success(self, vector_store, mock_tracer):
        """Test successful search for vectors."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "data": [
                {
                    "id": "doc1_id",
                    "key": "doc1",
                    "distance": 0.85,
                    "metadata": {"source": "test"}
                },
                {
                    "id": "doc2_id",
                    "key": "doc2",
                    "distance": 0.75,
                    "metadata": {"source": "test"}
                }
            ]
        }
        
        with patch("httpx.post", return_value=mock_response):
            results = await vector_store.search(
                "test_collection", 
                "test query", 
                limit=5, 
                similarity=0.7,
                metadata={"filter": "test"}
            )
            
            assert len(results) == 2
            assert isinstance(results[0], VectorSearchResult)
            assert results[0].id == "doc1_id"
            assert results[0].key == "doc1"
            assert results[0].distance == 0.85
            assert results[1].id == "doc2_id"
            assert results[1].distance == 0.75
            
            httpx.post.assert_called_once()
            args, kwargs = httpx.post.call_args
            
            assert args[0] == "https://api.example.com/vector/search/test_collection"
            assert kwargs["headers"]["Authorization"] == "Bearer test_api_key"
            assert kwargs["json"]["query"] == "test query"
            assert kwargs["json"]["limit"] == 5
            assert kwargs["json"]["similarity"] == 0.7
            assert kwargs["json"]["metadata"] == {"filter": "test"}
            
            span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
            span.set_attribute.assert_any_call("name", "test_collection")
            span.set_attribute.assert_any_call("query", "test query")
            span.set_attribute.assert_any_call("limit", 5)
            span.set_attribute.assert_any_call("similarity", 0.7)
            span.add_event.assert_called_once_with("hit")
            span.set_status.assert_called_once_with(trace.StatusCode.OK)
    
    @pytest.mark.asyncio
    async def test_search_not_found(self, vector_store, mock_tracer):
        """Test search with no matching results."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404
        
        with patch("httpx.post", return_value=mock_response):
            results = await vector_store.search("test_collection", "test query")
            
            assert len(results) == 0
            
            span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
            span.add_event.assert_called_once_with("miss")
            span.set_status.assert_called_once_with(trace.StatusCode.OK)
    
    @pytest.mark.asyncio
    async def test_search_error(self, vector_store, mock_tracer):
        """Test error handling during search operation."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        
        with patch("httpx.post", return_value=mock_response), \
             pytest.raises(Exception, match="Failed to search documents: 500"):
            await vector_store.search("test_collection", "test query")
            
            span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
            span.set_status.assert_called_once_with(
                trace.StatusCode.ERROR, 
                "Failed to search documents"
            )
    
    @pytest.mark.asyncio
    async def test_delete_success(self, vector_store, mock_tracer):
        """Test successful deletion of vectors."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "data": 2  # Number of vectors deleted
        }
        
        with patch("httpx.delete", return_value=mock_response):
            count = await vector_store.delete("test_collection", "doc1")
            
            assert count == 2
            
            httpx.delete.assert_called_once()
            args, kwargs = httpx.delete.call_args
            
            assert args[0] == "https://api.example.com/vector/test_collection/doc1"
            assert kwargs["headers"]["Authorization"] == "Bearer test_api_key"
            
            span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
            span.set_attribute.assert_any_call("name", "test_collection")
            span.set_attribute.assert_any_call("key", "doc1")
            span.add_event.assert_called_once()
            span.set_status.assert_called_once_with(trace.StatusCode.OK)
    
    @pytest.mark.asyncio
    async def test_delete_error(self, vector_store, mock_tracer):
        """Test error handling during delete operation."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        
        with patch("httpx.delete", return_value=mock_response), \
             pytest.raises(Exception, match="Failed to delete documents: 500"):
            await vector_store.delete("test_collection", "doc1")
            
            span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
            span.set_status.assert_called_once_with(
                trace.StatusCode.ERROR, 
                "Failed to delete documents"
            )
