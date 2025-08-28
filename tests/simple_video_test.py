#!/usr/bin/env python3
"""
Simple video generation test using the fixed code.
"""

import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai.types import GenerateVideosConfig, Image

# Load environment variables
load_dotenv()

def test_video_generation():
    """Test video generation with proper error handling."""
    
    print("🎬 Testing Video Generation...")
    
    # Set up environment
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"
    
    # Check required environment variables
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    bucket = os.getenv("GOOGLE_CLOUD_STORAGE_BUCKET")
    
    if not project:
        print("❌ GOOGLE_CLOUD_PROJECT environment variable not set")
        return
    
    if not bucket:
        print("❌ GOOGLE_CLOUD_STORAGE_BUCKET environment variable not set")
        return
    
    print(f"📊 Project: {project}")
    print(f"📊 Location: {location}")
    print(f"📊 Bucket: {bucket}")
    
    try:
        # Initialize client
        client = genai.Client(
            vertexai=True,
            project=project,
            location=location,
        )
        
        # Test parameters
        gcs_image_uri = "gs://cloud-samples-data/generative-ai/image/flowers.png"
        video_prompt = "Extreme close-up of a cluster of vibrant wildflowers swaying gently in a sun-drenched meadow."
        output_gcs_uri = f"gs://{bucket}/test_videos/flowers_test.mp4"
        
        print(f"📸 Input Image: {gcs_image_uri}")
        print(f"📝 Prompt: {video_prompt}")
        print(f"📤 Output: {output_gcs_uri}")
        print("\n⏳ Starting video generation...")
        
        # Generate video
        operation = client.models.generate_videos(
            model="veo-3.0-generate-preview",
            prompt=video_prompt,
            image=Image(
                gcs_uri=gcs_image_uri,
                mime_type="image/png",
            ),
            config=GenerateVideosConfig(
                aspect_ratio="16:9",
                output_gcs_uri=output_gcs_uri,
            ),
        )
        
        # Poll for completion with timeout
        max_wait_time = 600  # 10 minutes
        wait_time = 0
        
        while not operation.done and wait_time < max_wait_time:
            time.sleep(15)
            wait_time += 15
            operation = client.operations.get(operation)
            print(f"⏳ Video generation in progress... ({wait_time}s elapsed)")
        
        if wait_time >= max_wait_time:
            print("⏰ Video generation timed out after 10 minutes")
            return
        
        # Check results
        if operation.result and operation.result.generated_videos:
            video_uri = operation.result.generated_videos[0].video.uri
            print(f"✅ Success! Video generated at: {video_uri}")
        else:
            error_msg = operation.error if hasattr(operation, 'error') else 'Unknown error'
            print(f"❌ Video generation failed: {error_msg}")
            
    except Exception as e:
        print(f"💥 Error: {str(e)}")
        print("\n🔧 Troubleshooting tips:")
        print("1. Make sure you have the correct Google Cloud project ID")
        print("2. Ensure your GCS bucket exists and you have permissions")
        print("3. Check that Vertex AI API is enabled in your project")
        print("4. Verify your authentication is set up correctly")

if __name__ == "__main__":
    test_video_generation()
