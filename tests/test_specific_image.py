#!/usr/bin/env python3
"""Test video generation with the specific image."""

import os
import asyncio
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

async def test_specific_image():
    """Test with the specific wooden spice box image."""
    
    print("Testing video generation with wooden spice box image...")
    
    try:
        from artisan_agent.sub_agents.artisan_video.agent import generate_artisan_video
        
        # Test parameters
        gcs_image_uri = "gs://artisan_app/artisan_input/5_2331028b-d8c8-46a2-88b6-268673847445.png"
        video_prompt = "Generate a promotional video for a wooden spice box. The video should be a beautiful, rotating showcase of the box, highlighting the intricate wood grain and craftsmanship. Use a warm, inviting tone."
        
        print(f"Image: {gcs_image_uri}")
        print(f"Prompt: {video_prompt}")
        print(f"Project: {os.getenv('GOOGLE_CLOUD_PROJECT')}")
        print(f"Bucket: {os.getenv('GOOGLE_CLOUD_STORAGE_BUCKET')}")
        
        result = await generate_artisan_video(
            gcs_image_uri=gcs_image_uri,
            video_prompt=video_prompt
        )
        
        print(f"\nResult: {result}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_specific_image())
