"""Artisan Image Agent using independent Nano Banana server."""

import os
from google.genai.types import GenerateContentConfig, Modality
from google.adk import Agent
from google.adk.tools import load_artifacts, ToolContext
from dotenv import load_dotenv
from google import genai
from ...logger import get_logger
from . import prompt
from google.cloud import storage
import uuid
import time
logger = get_logger(__name__)

MODEL = "gemini-2.5-pro"

NANO_BANANA_MODEL = "gemini-2.5-flash-image-preview"

# Image generation configuration
MAX_WAIT_TIME = 600          # Maximum wait time in seconds (10 minutes)
POLL_INTERVAL = 10     

load_dotenv()

# Set environment variables for Vertex AI
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

client = genai.Client(
    vertexai=True,
    project=os.getenv("GOOGLE_CLOUD_PROJECT"),
    location=os.getenv("GOOGLE_CLOUD_LOCATION", "global"),
)

async def generate_artisan_variations(
    gcs_image_uri: str,
    image_prompt: str,
):
    """Generate artisan product image variations using Nano Banana MCP server.
    
    This function handles everything in one place:
    1. Downloads the input image from GCS (once)
    2. Generates variations using Nano Banana with custom prompts
    3. Uploads all results to GCS
    4. Returns the GCS URIs
    
    Args:
        gcs_image_uri: GCS URI of the input image
        image_prompt: Custom prompt for image variation
        tool_context: Optional tool context for artifacts
        
    Returns:
        JSON string with GCS URIs of generated images or None if failed
    """
    logger.info(f"Starting image generation workflow")
    logger.info(f"Input image URI: {gcs_image_uri}")
    logger.info(f"Using {image_prompt} custom prompts from agent")
    
    # Derive base name from input image
    base_name = os.path.splitext(os.path.basename(gcs_image_uri))[0]
    unique_name = f"{base_name}_{uuid.uuid4().hex}.png"

    # Build output GCS path
    output_gcs_uri = (
        f"gs://{os.getenv('GOOGLE_CLOUD_STORAGE_BUCKET')}/artisan_images/{unique_name}"
    )

    # Download input image from GCS to include alongside the text prompt
    if not gcs_image_uri.startswith("gs://"):
        return {"status": "failed", "detail": "gcs_image_uri must start with gs://"}

    _, _, bucket_and_path = gcs_image_uri.partition("gs://")
    bucket_name, _, blob_path = bucket_and_path.partition("/")
    if not bucket_name or not blob_path:
        return {"status": "failed", "detail": "Invalid GCS URI"}

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    image_bytes = blob.download_as_bytes()

    ext = os.path.splitext(blob_path)[-1].lower()
    mime_type = "image/jpeg" if ext in [".jpg", ".jpeg"] else "image/png"

    try:
        logger.info(f"Initiating image generation with Veo model: {NANO_BANANA_MODEL}")
        start_time = time.time()
        response = client.models.generate_content(
            model=NANO_BANANA_MODEL,
            contents=(
                {"inline_data": {"mime_type": mime_type, "data": image_bytes}},
                image_prompt,
            ),
            config=GenerateContentConfig(response_modalities=[Modality.TEXT, Modality.IMAGE]),
        )
        generation_time = time.time() - start_time
        logger.info(f"Image generation completed in {generation_time:.2f} seconds")

        first_image_bytes = None
        for part in response.candidates[0].content.parts:
            if getattr(part, "inline_data", None):
                first_image_bytes = part.inline_data.data
                break

        if not first_image_bytes:
            logger.error("No image returned by the model")
            return {"status": "failed", "detail": "No image returned"}

        # Upload generated image to output GCS URI
        _, _, out_bucket_and_path = output_gcs_uri.partition("gs://")
        out_bucket_name, _, out_blob_path = out_bucket_and_path.partition("/")
        out_bucket = storage_client.bucket(out_bucket_name)
        out_blob = out_bucket.blob(out_blob_path)
        out_blob.upload_from_string(first_image_bytes, content_type=mime_type)

        return {
            "status": "success",
            "detail": "Artisan image generated successfully",
            "image_uri": output_gcs_uri,
        }

    except Exception as e:
        logger.error(f"Exception during image generation: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "detail": f"Error during image generation: {str(e)}"
        }

# Define the MCP-based image agent
artisan_image_agent = Agent(
    model=MODEL,
    name="artisan_image_agent",
    description=(
        "An agent that generates artisan product images using independent Nano Banana server. "
        "Takes prompts and GCS image URIs to create professional product variations."
    ),
    instruction=prompt.ARTISAN_IMAGE_PROMPT,
    output_key="artisan_image_output",
    tools=[generate_artisan_variations, load_artifacts],
)

logger.info("Banana Image agent initialized successfully")
