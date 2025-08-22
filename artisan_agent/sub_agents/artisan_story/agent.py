"""Domain_create_agent: for suggesting meanigful DNS domain"""

from google.adk import Agent
from google.adk.tools import google_search

from . import prompt

MODEL = "gemini-2.5-pro" 

artisan_story_agent = Agent(
    model=MODEL,
    name="artisan_story_agent",
    instruction=prompt.ARTISAN_STORY_PROMPT,
    output_key="artisan_story_output",
    tools=[google_search],
)