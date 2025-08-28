#!/usr/bin/env python3
"""
Test script for video generation to debug issues.
Run this to verify your setup and identify problems.
"""

import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai.types import GenerateVideosConfig, Image

load_dotenv()

def test_video_generation():
    """Test video generation with a sample image."""
    
    # Check environment variables
    print("=== Environment Check ===")
    required_vars = ["GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION", "GOOGLE_CLOUD_STORAGE_BUCKET"]
    for var in required_vars:
        value = os.getenv(var)
        print(f"{var}: {'✓ Set' if value else '✗ Missing'}")
        if value:
            print(f"  Value: {value}")
    
    # Check if all required vars are set
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        print(f"\n❌ Missing environment variables: {', '.join(missing_vars)}")
        print("Please set these in your .env file")
        return False
    
    print("\n=== Client Setup ===")
    try:
        # Use the same setup as the documentation
        genai.configure(
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("GOOGLE_CLOUD_LOCATION"),
        )
        client = genai.Client()
        print("✓ Client created successfully")
    except Exception as e:
        print(f"❌ Failed to create client: {e}")
        return False
    
    # Test with a sample image from Google Cloud samples
    print("\n=== Video Generation Test ===")
    sample_image_uri = "gs://cloud-samples-data/generative-ai/image/flowers.png"
    test_prompt = "Extreme close-up of a cluster of vibrant wildflowers swaying gently in a sun-drenched meadow."
    output_uri = f"gs://{os.getenv('GOOGLE_CLOUD_STORAGE_BUCKET')}/test_video_{int(time.time())}.mp4"
    
    print(f"Sample image: {sample_image_uri}")
    print(f"Test prompt: {test_prompt}")
    print(f"Output URI: {output_uri}")
    
    try:
        print("\nStarting video generation...")
        operation = client.models.generate_videos(
            model="veo-3.0-generate-preview",
            prompt=test_prompt,
            image=Image(
                gcs_uri=sample_image_uri,
                mime_type="image/png",
            ),
            config=GenerateVideosConfig(
                aspect_ratio="16:9",
                output_gcs_uri=output_uri,
            ),
        )
        
        print(f"✓ Operation started: {operation.name}")
        
        # Poll for completion (following documentation pattern)
        max_attempts = 20  # 5 minutes max
        attempts = 0
        
        while not operation.done and attempts < max_attempts:
            time.sleep(15)
            operation = client.operations.get(operation)
            attempts += 1
            print(f"Polling attempt {attempts}/{max_attempts} - Done: {operation.done}")
            
            if operation.done:
                if operation.response:
                    print("✓ Video generation completed successfully!")
                    # Use the documentation's result access pattern
                    if hasattr(operation, 'result') and operation.result and operation.result.generated_videos:
                        video_uri = operation.result.generated_videos[0].video.uri
                        print(f"Generated video: {video_uri}")
                        return True
                    else:
                        print("❌ No videos in result")
                        return False
                elif operation.error:
                    print(f"❌ Video generation failed: {operation.error.message}")
                    return False
                else:
                    print("❌ Unknown error in operation")
                    return False
        
        if attempts >= max_attempts:
            print("❌ Video generation timed out")
            return False
            
    except Exception as e:
        print(f"❌ Exception during video generation: {e}")
        return False

if __name__ == "__main__":
    print("Video Generation Test Script")
    print("=" * 50)
    
    success = test_video_generation()
    
    if success:
        print("\n🎉 Test completed successfully!")
    else:
        print("\n💥 Test failed. Check the errors above.")
