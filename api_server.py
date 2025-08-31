"""FastAPI server to expose the Artisan Agent directly via REST API."""

import os
import asyncio
import logging
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Import centralized logging
from artisan_agent.logger import get_logger

logger = get_logger(__name__)

# Load environment variables
load_dotenv()

# Import ADK components
try:
    from vertexai.preview.reasoning_engines import AdkApp
    from artisan_agent.agent import root_agent
    
    # Create ADK app wrapper
    app_wrapper = AdkApp(agent=root_agent)
    logger.info("Agent loaded successfully")
    
except ImportError as e:
    logger.error(f"Could not import ADK components: {e}")
    logger.info("Make sure you have installed: pip install google-cloud-aiplatform")
    app_wrapper = None
except Exception as e:
    logger.error(f"Error initializing agent: {e}")
    app_wrapper = None

app = FastAPI(
    title="Artisan Agent API",
    description="Direct API for the Artisan Agent - creates stories, videos, and enhanced content for artisan products",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for your specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response Models
class GenerateRequest(BaseModel):
    """Request model for content generation."""
    product_description: str = Field(..., description="Description or name of the artisan product")
    gcs_image_uri: str = Field(..., description="GCS URI of the product image (required for video generation)")
    user_id: str = Field(default="default_user", description="User identifier")
    
    class Config:
        schema_extra = {
            "example": {
                "product_description": "Handcrafted Wooden Spice Box",
                "gcs_image_uri": "gs://your-bucket/images/spice_box.jpg",
                "user_id": "user123"
            }
        }

# Removed ChatRequest - using only GenerateRequest for simplicity

class ApiResponse(BaseModel):
    """Standard API response."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    processing_time_seconds: Optional[float] = None
    error: Optional[str] = None

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    agent_available: bool
    environment_ready: bool
    required_env_vars: Dict[str, bool]

# Validation functions
def validate_request(request: GenerateRequest) -> None:
    """
    Perform sanity checks on the request.
    
    Args:
        request: The GenerateRequest to validate
        
    Raises:
        HTTPException: If validation fails
    """
    
    if not request.user_id:
        logger.warning("Missing required user ID")
        raise HTTPException(
            status_code=400,
            detail="User ID is required for content generation"
        )

    logger.debug(f"Validating request for user: {request.user_id}")
    
    # 1. Product description validation
    if not request.product_description or len(request.product_description.strip()) == 0:
        logger.warning("Empty or missing product description")
        raise HTTPException(
            status_code=400,
            detail="Product description is required and cannot be empty"
        )
    
    # 2. GCS URI validation (now required)
    if not request.gcs_image_uri:
        logger.warning("Missing required GCS image URI")
        raise HTTPException(
            status_code=400,
            detail="GCS image URI is required for content generation"
        )
    
    if not request.gcs_image_uri.startswith("gs://"):
        logger.warning(f"Invalid GCS URI format: {request.gcs_image_uri}")
        raise HTTPException(
            status_code=400,
            detail="GCS image URI must start with 'gs://' (example: gs://bucket-name/image.jpg)"
        )
    
    # Check for image file extensions
    valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
    if not any(request.gcs_image_uri.lower().endswith(ext) for ext in valid_extensions):
        logger.warning(f"GCS URI doesn't appear to be an image file: {request.gcs_image_uri}")
        raise HTTPException(
            status_code=400,
            detail=f"GCS URI should point to an image file ({', '.join(valid_extensions)})"
        )

    
    logger.debug("Request validation passed successfully")

# Health check endpoint
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check if the API and agent are working properly."""
    logger.info("Health check requested")
    
    required_vars = {
        "GOOGLE_CLOUD_PROJECT": bool(os.getenv("GOOGLE_CLOUD_PROJECT")),
        "GOOGLE_CLOUD_LOCATION": bool(os.getenv("GOOGLE_CLOUD_LOCATION")),
        "GOOGLE_APPLICATION_CREDENTIALS": bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS")) or bool(os.getenv("GOOGLE_CLOUD_CREDENTIALS"))
    }
    
    health_status = "healthy" if app_wrapper else "unhealthy"
    logger.info(f"Health check result: {health_status}, agent_available: {app_wrapper is not None}")
    
    return HealthResponse(
        status=health_status,
        agent_available=app_wrapper is not None,
        environment_ready=all(required_vars.values()),
        required_env_vars=required_vars
    )

# Main generation endpoint
@app.post("/generate", response_model=ApiResponse)
async def generate_content(request: GenerateRequest):
    """
    Generate comprehensive artisan content (story, history, FAQs, and video).
    
    Takes a product description and image, then autonomously generates all marketing content.
    Video generation can take up to 10 minutes.
    """
    logger.info(f"Content generation requested by user: {request.user_id}")
    logger.info(f"Product: {request.product_description}..., Image URI provided: {bool(request.gcs_image_uri)}")
    
    # Perform validation
    validate_request(request)
    
    if app_wrapper is None:
        logger.error("Agent service unavailable - no app_wrapper")
        raise HTTPException(
            status_code=503, 
            detail="Agent service unavailable. Check logs and environment configuration."
        )
    
    logger.info("All validation checks passed, proceeding with content generation")
    
    import time
    start_time = time.time()
    
    try:
        # Build the prompt for the coordinator agent
        prompt_parts = [
            f"Product: {request.product_description}",
            f"Image GCS URI: {request.gcs_image_uri}",
            "Please generate comprehensive marketing content including story, history, FAQs, and promotional video."
        ]
        
        prompt = "\n".join(prompt_parts)
        logger.info("Sending request to main agent for autonomous processing")
        logger.debug(f"Generated prompt: {prompt[:200]}...")
        
        # Collect all events from the agent
        events = []
        final_response = None
        
        # Set timeout for full content generation (including video)
        timeout = 600  # 10 minutes for complete generation
        logger.info(f"Starting agent processing with timeout: {timeout}s")
        
        # Get the async generator and iterate with timeout handling
        stream = app_wrapper.async_stream_query(
            user_id=request.user_id,
            message=prompt,
        )
        
        # Track start time for timeout
        start_iteration = time.time()
        
        async for event in stream:
            # Check for timeout
            if time.time() - start_iteration > timeout:
                raise asyncio.TimeoutError("Stream processing timed out")
                
            events.append(event)
            logger.debug(f"Received event from agent: {event.get('author', 'unknown')}")
            
            # Get the final response from the agent
            if event.get('content', {}).get('parts'):
                for part in event['content']['parts']:
                    if 'text' in part and part['text'].strip():
                        final_response = part['text']
                        logger.debug(f"Found text response: {part['text'][:200]}...")
        
        processing_time = time.time() - start_time
        logger.info(f"Content generation completed successfully in {processing_time:.2f}s")
        
        if not final_response:
            logger.error("No final response received from agent")
            raise HTTPException(
                status_code=500,
                detail="No response received from agent"
            )
        
        # Clean up markdown formatting and parse JSON
        try:
            import json
            
            # Remove markdown code block formatting if present
            clean_response = final_response.strip()
            if clean_response.startswith("```json"):
                clean_response = clean_response.replace("```json", "").replace("```", "").strip()
            elif clean_response.startswith("```"):
                clean_response = clean_response.replace("```", "").strip()
            
            agent_data = json.loads(clean_response)
            logger.info("Successfully parsed agent JSON response")
            
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to parse agent response as JSON: {e}")
            logger.error(f"Raw response: {final_response[:500]}...")
            raise HTTPException(
                status_code=500,
                detail=f"Agent returned invalid JSON: {str(e)}"
            )
        
        return ApiResponse(
            success=True,
            message="Content generated successfully",
            data=agent_data,  # Just the clean JSON content from the main agent
            processing_time_seconds=round(processing_time, 2)
        )
        
    except asyncio.TimeoutError:
        processing_time = time.time() - start_time
        logger.error(f"Content generation timed out after {processing_time:.2f}s")
        raise HTTPException(
            status_code=408,
            detail=f"Content generation timed out (10 minutes max). Processing time: {processing_time:.2f} seconds"
        )
    except Exception as e:
        processing_time = time.time() - start_time
        raise HTTPException(
            status_code=500,
            detail=f"Error generating content: {str(e)}. Processing time: {processing_time:.2f} seconds"
        )

# Removed separate endpoints - main agent handles everything autonomously

# Development helper endpoints
@app.get("/")
async def root():
    """API root with basic information."""
    return {
        "service": "Artisan Agent API",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "generate": "POST /generate - Generate story, history, FAQs, and video for artisan products"
        },
        "description": "Provide product description + image URI → Get comprehensive marketing content"
    }

if __name__ == "__main__":
    import uvicorn 
    
    print("🚀 Starting Artisan Agent API server...")
    print("📚 API documentation: http://localhost:8000/docs")
    print("❤️ Health check: http://localhost:8000/health")
    print("🎨 Main endpoint: http://localhost:8000/generate")
    
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
