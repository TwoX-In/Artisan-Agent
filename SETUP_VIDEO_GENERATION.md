# Video Generation Setup Guide

This guide will help you set up video generation using Google's Veo model via Vertex AI.

## Prerequisites

1. **Google Cloud Project**: You need a Google Cloud project with billing enabled
2. **Vertex AI API**: Enable the Vertex AI API in your project
3. **Authentication**: Set up Application Default Credentials (ADC)
4. **GCS Bucket**: Create a Google Cloud Storage bucket for storing videos

## Step 1: Environment Setup

1. Create a `.env` file in your project root:
```bash
cp .env.template .env
```

2. Edit the `.env` file with your actual values:
```env
GOOGLE_CLOUD_PROJECT=your-actual-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_CLOUD_STORAGE_BUCKET=your-bucket-name
GOOGLE_GENAI_USE_VERTEXAI=True
```

## Step 2: Google Cloud Setup

1. **Install Google Cloud CLI**:
```bash
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
```

2. **Authenticate**:
```bash
gcloud auth login
gcloud auth application-default login
```

3. **Set your project**:
```bash
gcloud config set project YOUR_PROJECT_ID
```

4. **Enable required APIs**:
```bash
gcloud services enable aiplatform.googleapis.com
gcloud services enable storage.googleapis.com
```

5. **Create a GCS bucket** (if you don't have one):
```bash
gsutil mb gs://your-bucket-name
```

## Step 3: Install Dependencies

Make sure you have all required Python packages:
```bash
pip install -r requirements.txt
```

## Step 4: Test Your Setup

1. **Check environment**:
```bash
python check_env.py
```

2. **Test video generation**:
```bash
python simple_video_test.py
```

Or test the existing test script:
```bash
python test_video_generation.py
```

## Step 5: Using the Agent

```python
from artisan_agent.sub_agents.artisan_video.agent import generate_artisan_video
import asyncio

async def main():
    result = await generate_artisan_video(
        gcs_image_uri="gs://your-bucket/path/to/image.png",
        video_prompt="Create a beautiful cinematic video showing the product"
    )
    print(result)

asyncio.run(main())
```

## Troubleshooting

### Common Issues

1. **Authentication Error**: 
   - Run `gcloud auth application-default login`
   - Make sure your project ID is correct

2. **Permission Denied**:
   - Ensure Vertex AI API is enabled
   - Check that your account has necessary permissions

3. **Bucket Not Found**:
   - Verify the bucket name in your `.env` file
   - Make sure the bucket exists and you have access

4. **Import Errors**:
   - Check that all dependencies are installed
   - Make sure you're using the correct Python environment

### Verification Commands

```bash
# Check if APIs are enabled
gcloud services list --enabled | grep aiplatform

# Check authentication
gcloud auth list

# Test bucket access
gsutil ls gs://your-bucket-name

# Check Vertex AI quota
gcloud ai operations list --region=us-central1
```

## Cost Considerations

- Veo video generation costs approximately $0.50-1.00 per video
- Videos are limited to 8 seconds in the preview version
- Monitor your usage in the Google Cloud Console

## Support

- Check the [Vertex AI documentation](https://cloud.google.com/vertex-ai/generative-ai/docs)
- Review [Veo model documentation](https://cloud.google.com/vertex-ai/generative-ai/docs/image-generation)
- For billing questions, check the [pricing page](https://cloud.google.com/vertex-ai/pricing)
