import os
from dotenv import load_dotenv
from google.adk import Agent
from google.adk.tools import ToolContext, load_artifacts
from google.genai import Client, types

from . import prompt

MODEL = "gemini-2.5-pro"
MODEL_VIDEO = "veo-3.0-fast-generate-preview"

load_dotenv()

# Initialize Vertex AI client
client = Client(
    vertexai=True,
    project=os.getenv("GOOGLE_CLOUD_PROJECT"),
    location=os.getenv("GOOGLE_CLOUD_LOCATION"),
)

async def generate_video_reel(
    tool_context: ToolContext,
    product_name: str,
    product_description: str,
    descriptive_history: str
):
    """Generates an Instagram-ready video using saved refined images."""

    # Load all saved image artifacts
    artifacts = await tool_context.load_artifacts()
    image_filenames = list(artifacts.keys())
    if not image_filenames:
        return {"status": "failed", "detail": "No saved images found for video generation."}

    # Prepare prompt with inputs
    video_prompt = prompt.ARTISAN_VIDEO_PROMPT.format(
        images=image_filenames,
        product_name=product_name,
        product_description=product_description,
        descriptive_history=descriptive_history,
    )

    # Generate video using Veo model
    response = client.models.generate_video(
        model=MODEL_VIDEO,
        prompt=video_prompt,
        config={"number_of_videos": 1},
    )

    if not response.generated_videos:
        return {"status": "failed", "detail": "Video generation failed."}

    video_bytes = response.generated_videos[0].video_bytes

    # Save generated video as an artifact
    await tool_context.save_artifact(
        "artisan_video_reel.mp4",
        types.Part.from_bytes(data=video_bytes, mime_type="video/mp4"),
    )

    return {
        "status": "success",
        "detail": "Video reel generated successfully and stored in artifacts.",
        "filename": "artisan_video_reel.mp4",
    }


# Define the artisan video agent
artisan_video_agent = Agent(
    model=MODEL,  # model for controlling the agent instructions
    name="artisan_video_agent",
    description=(
        "An agent that generates Instagram-ready video reels using pre-refined artisan product images."
    ),
    instruction=prompt.ARTISAN_VIDEO_PROMPT,
    output_key="artisan_video_output",
    tools=[generate_video_reel, load_artifacts],
)
