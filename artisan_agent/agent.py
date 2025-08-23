"""Defines the main agent for coordinating artisan creation tasks."""

from google.adk.agents import LlmAgent
from google.adk.tools.agent_tool import AgentTool

from . import prompt
from .sub_agents.artisan_image import artisan_image_agent
from .sub_agents.artisan_story import artisan_story_agent
from .sub_agents.artisan_video import artisan_video_agent

MODEL = "gemini-2.5-pro" 

artisan_coordinator = LlmAgent(
    name="artisan_coordinator",
    model=MODEL,
    description=(
        "A coordinator agent that manages the workflow of creating artisan product images, "
        "stories, and videos by delegating tasks to specialized sub-agents."
    ),
    instruction=prompt.ARTISAN_COORDINATOR_PROMPT,
    tools=[
        AgentTool(agent=artisan_image_agent),
        AgentTool(agent=artisan_story_agent),
        AgentTool(agent=artisan_image_agent),
    ],
)

root_agent = artisan_coordinator