"""artisan_image sub-agent for image refinement tasks"""

import os
from dotenv import load_dotenv
from google.adk import Agent
from google.adk.tools import ToolContext, load_artifacts
from google.genai import Client, types

from . import prompt  # ensure you have prompt.py with ARTISAN_IMAGE_PROMPT

MODEL = "gemini-2.5-pro"
MODEL_IMAGE = "imagen-3.0-capability-001"  # editing-capable Imagen model

# Load environment variables
load_dotenv()

# Initialize client (Vertex AI only supports image gen/edit for now)
client = Client(
    vertexai=True,
    project=os.getenv("GOOGLE_CLOUD_PROJECT"),
    location=os.getenv("GOOGLE_CLOUD_LOCATION"),
)


async def refine_artisan_image(
    image_file: bytes,   # input image (PNG bytes)
    instruction: str,    # refinement instruction, e.g. "brighten background"
    tool_context: "ToolContext",
):
    """Refines an artisan image based on an input image + instruction."""

    response = client.models.generate_images(
        model=MODEL_IMAGE,
        prompt=instruction,
        image=types.Part.from_bytes(data=image_file, mime_type="image/png"),
        config={"number_of_images": 1},
    )

    if not response.generated_images:
        return {"status": "failed"}

    image_bytes = response.generated_images[0].image.image_bytes

    # Save output as artifact
    await tool_context.save_artifact(
        "artisan_refined.png",
        types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
    )

    return {
        "status": "success",
        "detail": "Artisan image refined successfully and stored in artifacts.",
        "filename": "artisan_refined.png",
    }


# Define the sub-agent
artisan_image_agent = Agent(
    model=MODEL,
    name="artisan_image_agent",
    description=(
        "An agent that refines artisan product images "
        "using input images and textual instructions."
    ),
    instruction=prompt.ARTISAN_IMAGE_PROMPT,
    output_key="artisan_image_output",
    tools=[refine_artisan_image, load_artifacts],
)
