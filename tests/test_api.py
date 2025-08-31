#!/usr/bin/env python3
"""
Test script for the Artisan Agent API with mocked agent responses.
This allows testing the API logic without running the actual agent.
"""

import asyncio
import json
import time
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from fastapi.testclient import TestClient

# Import the API
from api_server import app

# Create test client
client = TestClient(app)

# Mock agent response that matches your expected format
MOCK_AGENT_RESPONSE = {
    "story": "Bring the heart of culinary tradition into your kitchen with our Handcrafted Wooden Spice Box. This beautifully designed container is not just a practical tool for organizing your most-used spices, but a piece of art that adds a warm, earthy elegance to your countertop.",
    "history": "The wooden spice box, often known as a 'masala dabba' in India, has a rich history deeply rooted in Indian culinary traditions. Its origins trace back to ancient India, where spices were crucial for both cooking and medicinal purposes.",
    "faqs": [
        {
            "question": "What is a wooden spice box traditionally used for?",
            "answer": "A wooden spice box, particularly the Indian 'masala dabba', is used to store and organize the most frequently used spices in one convenient location."
        },
        {
            "question": "What are the benefits of storing spices in a wooden box?",
            "answer": "Wood is a natural, non-toxic material that helps maintain a consistent temperature, which preserves the freshness and longevity of your spices."
        }
    ],
    "generated_video_url": "gs://artisan_app/artisan_videos/test_video.mp4"
}

def mock_agent_stream():
    """Mock the agent stream response."""
    yield {
        "author": "agent",
        "content": {
            "parts": [
                {"text": json.dumps(MOCK_AGENT_RESPONSE)}
            ]
        }
    }

class TestArtisanAPI:
    """Test suite for the Artisan Agent API."""
    
    def test_health_check(self):
        """Test the health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "agent_available" in data
    
    def test_root_endpoint(self):
        """Test the root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Artisan Agent API"
        assert "endpoints" in data
    
    @patch('api_server.app_wrapper')
    def test_generate_content_success(self, mock_app_wrapper):
        """Test successful content generation."""
        # Mock the agent wrapper
        mock_app_wrapper.async_stream_query = AsyncMock(return_value=mock_agent_stream())
        
        # Test request
        request_data = {
            "product_description": "Handcrafted Wooden Spice Box",
            "gcs_image_uri": "gs://test-bucket/spice_box.jpg",
            "user_id": "test_user_123"
        }
        
        response = client.post("/generate", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert data["success"] is True
        assert data["message"] == "Content generated successfully"
        assert "data" in data
        assert "content" in data["data"]
        assert "processing_time_seconds" in data
        
        # Verify content structure matches expected format
        content = data["data"]["content"]
        assert "story" in content
        assert "history" in content
        assert "faqs" in content
        assert "generated_video_url" in content
        
        # Verify request summary
        request_summary = data["data"]["request_summary"]
        assert request_summary["product"] == "Handcrafted Wooden Spice Box"
        assert request_summary["image_provided"] is True
        assert "story" in request_summary["content_types"]
        assert "video" in request_summary["content_types"]
    
    def test_validation_missing_product_description(self):
        """Test validation when product description is missing."""
        request_data = {
            "gcs_image_uri": "gs://test-bucket/spice_box.jpg",
            "user_id": "test_user"
        }
        
        response = client.post("/generate", json=request_data)
        assert response.status_code == 422  # Validation error
    
    def test_validation_empty_product_description(self):
        """Test validation when product description is empty."""
        request_data = {
            "product_description": "",
            "gcs_image_uri": "gs://test-bucket/spice_box.jpg",
            "user_id": "test_user"
        }
        
        response = client.post("/generate", json=request_data)
        assert response.status_code == 400
        assert "Product description is required" in response.json()["detail"]
    
    def test_validation_missing_user_id(self):
        """Test validation when user ID is missing."""
        request_data = {
            "product_description": "Test Product",
            "gcs_image_uri": "gs://test-bucket/spice_box.jpg"
        }
        
        response = client.post("/generate", json=request_data)
        assert response.status_code == 422  # Validation error for required field
    
    def test_validation_empty_user_id(self):
        """Test validation when user ID is empty."""
        request_data = {
            "product_description": "Test Product",
            "gcs_image_uri": "gs://test-bucket/spice_box.jpg",
            "user_id": ""
        }
        
        response = client.post("/generate", json=request_data)
        assert response.status_code == 400
        assert "User ID is required" in response.json()["detail"]
    
    def test_validation_missing_gcs_uri(self):
        """Test validation when GCS URI is missing."""
        request_data = {
            "product_description": "Test Product",
            "user_id": "test_user"
        }
        
        response = client.post("/generate", json=request_data)
        assert response.status_code == 422  # Validation error
    
    def test_validation_invalid_gcs_uri_format(self):
        """Test validation with invalid GCS URI format."""
        request_data = {
            "product_description": "Test Product",
            "gcs_image_uri": "http://example.com/image.jpg",
            "user_id": "test_user"
        }
        
        response = client.post("/generate", json=request_data)
        assert response.status_code == 400
        assert "must start with 'gs://'" in response.json()["detail"]
    
    def test_validation_invalid_image_extension(self):
        """Test validation with invalid image file extension."""
        request_data = {
            "product_description": "Test Product",
            "gcs_image_uri": "gs://test-bucket/document.pdf",
            "user_id": "test_user"
        }
        
        response = client.post("/generate", json=request_data)
        assert response.status_code == 400
        assert "should point to an image file" in response.json()["detail"]
    
    @patch('api_server.app_wrapper')
    def test_agent_timeout(self, mock_app_wrapper):
        """Test timeout handling."""
        # Mock a timeout
        async def timeout_stream():
            await asyncio.sleep(2)  # This will timeout during test
            yield {"content": {"parts": [{"text": "test"}]}}
        
        mock_app_wrapper.async_stream_query = AsyncMock(return_value=timeout_stream())
        
        request_data = {
            "product_description": "Test Product",
            "gcs_image_uri": "gs://test-bucket/spice_box.jpg",
            "user_id": "test_user"
        }
        
        # Mock asyncio.wait_for to simulate timeout
        with patch('asyncio.wait_for', side_effect=asyncio.TimeoutError()):
            response = client.post("/generate", json=request_data)
            assert response.status_code == 408
            assert "timed out" in response.json()["detail"]
    
    @patch('api_server.app_wrapper')
    def test_agent_error(self, mock_app_wrapper):
        """Test error handling during agent processing."""
        # Mock an exception
        mock_app_wrapper.async_stream_query = AsyncMock(side_effect=Exception("Agent error"))
        
        request_data = {
            "product_description": "Test Product",
            "gcs_image_uri": "gs://test-bucket/spice_box.jpg",
            "user_id": "test_user"
        }
        
        response = client.post("/generate", json=request_data)
        assert response.status_code == 500
        assert "Error generating content" in response.json()["detail"]
    
    def test_agent_unavailable(self):
        """Test behavior when agent is unavailable."""
        # Mock app_wrapper being None
        with patch('api_server.app_wrapper', None):
            request_data = {
                "product_description": "Test Product",
                "gcs_image_uri": "gs://test-bucket/spice_box.jpg",
                "user_id": "test_user"
            }
            
            response = client.post("/generate", json=request_data)
            assert response.status_code == 503
            assert "Agent service unavailable" in response.json()["detail"]

def run_manual_test():
    """Manual test function you can run directly."""
    print("🧪 Running manual API tests...")
    
    # Test health check
    print("\n1. Testing health check...")
    response = client.get("/health")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    
    # Test root endpoint
    print("\n2. Testing root endpoint...")
    response = client.get("/")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    
    # Test validation errors
    print("\n3. Testing validation errors...")
    
    # Missing product description
    response = client.post("/generate", json={
        "gcs_image_uri": "gs://test/image.jpg",
        "user_id": "test"
    })
    print(f"   Missing product: {response.status_code} - {response.json()}")
    
    # Invalid GCS URI
    response = client.post("/generate", json={
        "product_description": "Test Product",
        "gcs_image_uri": "http://invalid.com/image.jpg",
        "user_id": "test"
    })
    print(f"   Invalid GCS URI: {response.status_code} - {response.json()}")
    
    # Test with mock agent
    print("\n4. Testing with mocked agent...")
    with patch('api_server.app_wrapper') as mock_wrapper:
        mock_wrapper.async_stream_query = AsyncMock(return_value=mock_agent_stream())
        
        response = client.post("/generate", json={
            "product_description": "Handcrafted Wooden Spice Box",
            "gcs_image_uri": "gs://test-bucket/spice_box.jpg",
            "user_id": "test_user_123"
        })
        
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Success: {data['success']}")
            print(f"   Processing time: {data['processing_time_seconds']}s")
            print(f"   Content keys: {list(data['data']['content'].keys())}")
        else:
            print(f"   Error: {response.json()}")
    
    print("\n✅ Manual tests completed!")

if __name__ == "__main__":
    print("🚀 Artisan Agent API Test Suite")
    print("=" * 40)
    
    # Run manual tests
    run_manual_test()
    
    print("\n" + "=" * 40)
    print("💡 To run full pytest suite:")
    print("   pip install pytest pytest-asyncio")
    print("   pytest test_api.py -v")
