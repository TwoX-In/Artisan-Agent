import os
import time
import uuid
from dotenv import load_dotenv
from google.adk import Agent
from google import genai
from google.genai.types import GenerateVideosConfig, Image
from . import prompt

# LLM used for orchestration / reasoning in this sub-agent (not for Veo itself)
MODEL = "gemini-2.5-pro"

# Veo model: note 8s limit on preview/3.0 (and on 3.0-generate-001)
MODEL_VIDEO = "veo-3.0-generate-preview"

# Video generation configuration
MAX_WAIT_TIME = 600          # Maximum wait time in seconds (10 minutes)
POLL_INTERVAL = 15           # Polling interval in seconds
ASPECT_RATIO = "16:9"        # Default video aspect ratio

load_dotenv()

# Set environment variables for Vertex AI
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

client = genai.Client(
    vertexai=True,
    project=os.getenv("GOOGLE_CLOUD_PROJECT"),
    location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
)

async def generate_artisan_video(gcs_image_uri: str, video_prompt: str, aspect_ratio: str = ASPECT_RATIO):
    """
    Generates a video using a product image and a creative prompt.

    Args:
        gcs_image_uri (str): GCS URI of the input product image.
        video_prompt (str): Short text instruction describing video style.
        aspect_ratio (str): Video aspect ratio. For veo-3.0-generate-preview, only "16:9" is supported.

    Returns:
        dict: Status, detail message, and output GCS video URI.
    """
    # Derive base name from input image
    base_name = os.path.splitext(os.path.basename(gcs_image_uri))[0]
    unique_name = f"{base_name}_{uuid.uuid4().hex}.mp4"

    # Build output GCS path
    output_gcs_uri = (
        f"gs://{os.getenv('GOOGLE_CLOUD_STORAGE_BUCKET')}/artisan_videos/{unique_name}"
    )

    # Infer mime type from extension (default to png)
    ext = os.path.splitext(gcs_image_uri)[-1].lower()
    mime_type = "image/jpeg" if ext in [".jpg", ".jpeg"] else "image/png"

    try:
        operation = client.models.generate_videos(
            model=MODEL_VIDEO,
            prompt=video_prompt,
            image=Image(
                gcs_uri=gcs_image_uri,
                mime_type=mime_type,
            ),
                    config=GenerateVideosConfig(
            aspect_ratio=aspect_ratio,  # Use provided aspect ratio (default 16:9)
            output_gcs_uri=output_gcs_uri,
        ),
        )

        # Poll until video generation is done
        max_wait_time = MAX_WAIT_TIME  # 10 minutes max wait time
        wait_time = 0
        
        while not operation.done and wait_time < max_wait_time:
            time.sleep(POLL_INTERVAL)
            wait_time += POLL_INTERVAL
            operation = client.operations.get(operation)
            print(f"Video generation in progress... ({wait_time}s elapsed)")

        if wait_time >= max_wait_time:
            return {
                "status": "timeout", 
                "detail": "Video generation timed out after MAX_WAIT_TIME minutes"
            }

        if operation.result and operation.result.generated_videos:
            video_uri = operation.result.generated_videos[0].video.uri
            return {
                "status": "success",
                "detail": "Artisan video generated successfully",
                "video_uri": video_uri,
            }
        else:
            return {
                "status": "failed", 
                "detail": f"Video generation failed: {operation.error if hasattr(operation, 'error') else 'Unknown error'}"
            }

    except Exception as e:
        return {
            "status": "error",
            "detail": f"Error during video generation: {str(e)}"
        }


# Sub-agent definition:
artisan_video_agent = Agent(
    model=MODEL,
    name="artisan_video_agent",
    description="Generates short-form videos (8-10 seconds) from artisan product images using Google's Veo model in 16:9 aspect ratio.",
    instruction=prompt.ARTISAN_VIDEO_PROMPT,
    output_key="artisan_video_output",
    tools=[generate_artisan_video],
)
