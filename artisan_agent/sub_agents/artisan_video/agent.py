import os
import base64
import asyncio
from dotenv import load_dotenv
from google.adk import Agent
from google.adk.tools import ToolContext, load_artifacts
from google.genai import Client
from google.genai.types import GenerateVideosConfig, Image

from . import prompt

MODEL = "gemini-2.5-pro"
MODEL_VIDEO = "veo-3.0-generate-preview"

load_dotenv()

client = Client(
    vertexai=True,
    project=os.getenv("GOOGLE_CLOUD_PROJECT"),
    location=os.getenv("GOOGLE_CLOUD_LOCATION"),
)


async def generate_video_reel(
    tool_context: ToolContext,
    product_name: str,
    product_description: str,
    descriptive_history: str,
    image_filename: str,
):
    """Generates an Instagram-ready video using a provided artisan product image."""

    # 1. Ensure the image exists in artifacts
    artifacts = await tool_context.list_artifacts()
    if image_filename not in artifacts:
        return {"status": "failed", "detail": f"Image {image_filename} not found in artifacts."}

    image_part = await tool_context.load_artifact(image_filename)
    if image_part.mime_type not in ["image/png", "image/jpeg"]:
        return {"status": "failed", "detail": f"Unsupported image MIME type: {image_part.mime_type}"}

    # 2. Encode image as Base64
    image_b64 = base64.b64encode(image_part.data).decode("utf-8")

    # 3. Build prompt (don’t .format() here, just embed variables into a new string)
    video_prompt = f"""
    Create an engaging 15-second artisan product reel.
    Product Name: {product_name}
    Description: {product_description}
    Story: {descriptive_history}
    Visual guidance from image: {image_filename}
    """

    try:
        # 4. Kick off async video generation
        operation = client.models.generate_videos(
            model=MODEL_VIDEO,
            prompt=video_prompt,
            image=Image(
                bytes_base64_encoded=image_b64,
                mime_type=image_part.mime_type,
            ),
            config=GenerateVideosConfig(
                duration_seconds=8,
                aspect_ratio="16:9",
                resolution="720p",
                sample_count=1,
                generate_audio=True,
            ),
        )

        # 5. Poll until complete
        while not operation.done:
            await asyncio.sleep(15)
            operation = client.operations.get(operation)

        if not operation.response:
            return {"status": "failed", "detail": "No video generated."}

        # 6. Handle output (GCS or inline bytes)
        result = operation.result.generated_videos[0].video

        if hasattr(result, "uri") and result.uri:
            return {
                "status": "success",
                "detail": "Video reel generated successfully.",
                "video_uri": result.uri,
            }
        elif hasattr(result, "bytes_base64_encoded"):
            return {
                "status": "success",
                "detail": "Video reel generated successfully (inline).",
                "video_bytes": result.bytes_base64_encoded,
            }
        else:
            return {"status": "failed", "detail": "Video generated but no URI or data returned."}

    except Exception as e:
        return {"status": "failed", "detail": f"Video generation error: {str(e)}"}


# 7. Agent definition
artisan_video_agent = Agent(
    model=MODEL,
    name="artisan_video_agent",
    description="Generates Instagram-ready video reels using a product image, name, description, and story.",
    instruction=prompt.ARTISAN_VIDEO_PROMPT,  # keep as reference prompt, not formatted
    output_key="artisan_video_output",
    tools=[generate_video_reel, load_artifacts],
)
