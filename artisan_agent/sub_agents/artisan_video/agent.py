import os
import time
import uuid
import tempfile
from typing import Optional
from dotenv import load_dotenv
from google.adk import Agent
from google import genai
from google.genai.types import GenerateVideosConfig, Image
from . import prompt
from ...logger import get_logger
from google.cloud import texttospeech
from google.cloud import storage
# FFmpegMCP imported dynamically in functions when needed

# Initialize logger for this module
logger = get_logger(__name__)

# LLM used for orchestration / reasoning in this sub-agent
MODEL = "gemini-2.5-pro"

# Veo model: note 8s limit on preview/3.0
MODEL_VIDEO = "veo-3.0-generate-preview"

MODEL_MUSIC = "lyria-002"

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
    location=os.getenv("GOOGLE_CLOUD_LOCATION"),
)

def upload_to_gcs(local_path: str, gcs_uri: str, content_type: str = "application/octet-stream") -> str:
    """
    Upload a local file to GCS and return the GCS URI.
    
    Args:
        local_path: Path to local file
        gcs_uri: Target GCS URI (gs://bucket/path)
        content_type: MIME type of the file
        
    Returns:
        The same GCS URI that was passed in
    """
    if not gcs_uri.startswith("gs://"):
        raise ValueError("GCS URI must start with gs://")
    
    # Parse bucket and blob name
    without_scheme = gcs_uri[5:]
    bucket_name, _, blob_name = without_scheme.partition("/")
    if not bucket_name or not blob_name:
        raise ValueError("GCS URI must be of the form gs://bucket/object")
    
    # Upload file
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(local_path, content_type=content_type)
    
    return gcs_uri


def download_to_temp(gcs_uri: str) -> str:
    """
    Download a GCS file to a temporary local file.
    
    Args:
        gcs_uri: GCS URI to download (gs://bucket/path)
        
    Returns:
        Path to the temporary local file
    """
    if not gcs_uri.startswith("gs://"):
        raise ValueError("GCS URI must start with gs://")
    
    # Parse bucket and blob name
    without_scheme = gcs_uri[5:]
    bucket_name, _, blob_name = without_scheme.partition("/")
    if not bucket_name or not blob_name:
        raise ValueError("GCS URI must be of the form gs://bucket/object")
    
    # Download to temp file
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    
    fd, tmp_path = tempfile.mkstemp()
    os.close(fd)
    blob.download_to_filename(tmp_path)
    
    return tmp_path

def generate_voiceover(text: str, product_name: str):
    """
    Generate narration in Indian English with Despina voice.
    Saves locally, optionally upload to GCS.
    """
    base_name = os.path.splitext(os.path.basename(product_name))[0]
    unique_name = f"{base_name}_{uuid.uuid4().hex}.wav"

    narration_path = f"/tmp/{unique_name}"  # local file
    try:
        tts_client = texttospeech.TextToSpeechClient()
        input_text = texttospeech.SynthesisInput(text=text)
        # Use a standard Indian English voice that doesn't require a model
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-IN",
            name="en-IN-Wavenet-A",   # or "en-IN-Wavenet-D"
            ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
        )

        audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.LINEAR16)

        response = tts_client.synthesize_speech(
            input=input_text, voice=voice, audio_config=audio_config
        )

        with open(narration_path, "wb") as out:
            out.write(response.audio_content)

        # Upload to GCS
        output_gcs_uri = f"gs://{os.getenv('GOOGLE_CLOUD_STORAGE_BUCKET')}/artisan_videos/{unique_name}"
        upload_to_gcs(narration_path, output_gcs_uri, "audio/wav")

        return {
            "status": "success",
            "detail": "Narration generated with Despina voice",
            "narration_path": narration_path,
            "audio_gcs_uri": output_gcs_uri,
        }
    except Exception as e:
        logger.error(f"Voiceover generation failed: {e}", exc_info=True)
        return {"status": "error", "detail": f"Voiceover generation failed: {e}"}

def generate_background_music(prompt: str, product_name: str):
    """
    Generate background music using Lyria-002 model via LyriaClient.
    
    Args:
        prompt: Text description of the desired music
        product_name: Used for generating unique filename
        
    Returns:
        dict with status, music_path (local), and audio_gcs_uri (GCS)
    """
    from .tools.lyria_client import LyriaClient
    
    try:
        # Create Lyria client
        lyria_client = LyriaClient(model=MODEL_MUSIC)
        
        # Generate music with GCS upload
        result = lyria_client.generate_music_with_gcs(
            prompt=prompt,
            product_name=product_name,
            seed=12345  # Use consistent seed for reproducible results
        )
        
        logger.info(f"Background music generation completed: {result['status']}")
        return result
        
    except Exception as e:
        logger.error(f"Background music generation failed: {e}", exc_info=True)
        return {"status": "error", "detail": f"Background music generation failed: {e}"}

async def generate_artisan_video(gcs_image_uri: str, video_prompt: str):
    """
    Generates a video using a product image and a video_prompt 

    Args:
        gcs_image_uri (str):
        video_prompt (str): 

    Returns:
        dict: Status, detail message, and output GCS video URI.
    """
    logger.info(f"Starting video generation for image: {gcs_image_uri}")
    logger.info(f"Video prompt: {video_prompt[:200]}{'...' if len(video_prompt) > 200 else ''}")
    
    # Derive base name from input image
    base_name = os.path.splitext(os.path.basename(gcs_image_uri))[0]
    unique_name = f"{base_name}_{uuid.uuid4().hex}"

    # Build output GCS path (no .mp4 extension - Veo will create its own file structure)
    output_gcs_uri = (
        f"gs://{os.getenv('GOOGLE_CLOUD_STORAGE_BUCKET')}/artisan_videos/{unique_name}"
    )

    # Infer mime type from extension (default to png)
    ext = os.path.splitext(gcs_image_uri)[-1].lower()
    mime_type = "image/jpeg" if ext in [".jpg", ".jpeg"] else "image/png"

    try:
        logger.info(f"Initiating video generation with Veo model: {MODEL_VIDEO}")
        operation = client.models.generate_videos(
            model=MODEL_VIDEO,
            prompt=video_prompt,  # Use the JSON video_prompt directly
            image=Image(
                gcs_uri=gcs_image_uri,
                mime_type=mime_type,
            ),
            config=GenerateVideosConfig(
                aspect_ratio=ASPECT_RATIO,  # Always use 16:9 as specified in prompt
                output_gcs_uri=output_gcs_uri,
            ),
        )
        
        logger.info(f"Video generation operation started: {operation.name}")

        # Poll until video generation is done
        max_wait_time = MAX_WAIT_TIME  # 10 minutes max wait time
        wait_time = 0
        logger.info(f"Starting polling for operation completion (max wait: {max_wait_time}s, interval: {POLL_INTERVAL}s)")
        
        while not operation.done and wait_time < max_wait_time:
            time.sleep(POLL_INTERVAL)
            wait_time += POLL_INTERVAL
            operation = client.operations.get(operation)
            logger.info(f"Video generation in progress... ({wait_time}s elapsed)")

        if wait_time >= max_wait_time:
            logger.error(f"Video generation timed out after {max_wait_time} seconds")
            return {
                "status": "timeout", 
                "detail": "Video generation timed out after MAX_WAIT_TIME minutes"
            }

        if operation.result and operation.result.generated_videos:
            video_uri = operation.result.generated_videos[0].video.uri
            logger.info(f"Video generation completed successfully! Video URI: {video_uri}")
            return {
                "status": "success",
                "detail": "Artisan video generated successfully",
                "video_uri": video_uri,
            }
        else:
            error_detail = operation.error if hasattr(operation, 'error') else 'Unknown error'
            logger.error(f"Video generation failed: {error_detail}")
            return {
                "status": "failed", 
                "detail": f"Video generation failed: {error_detail}"
            }

    except Exception as e:
        logger.error(f"Exception during video generation: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "detail": f"Error during video generation: {str(e)}"
        }

def process_videos_with_ffmpeg_mcp(video_uris: list, 
                                  narration_path: Optional[str] = None,
                                  music_path: Optional[str] = None,
                                  volume_prompt: str = ""):
    """
    Process videos using FFmpeg MCP class - handles transitions and audio stitching.
    
    Args:
        video_uris: List of local file paths or GCS URIs to videos
        narration_path: Optional local file path or GCS URI to narration audio
        music_path: Optional local file path or GCS URI to background music
        volume_prompt: Natural language prompt with volume instructions
        
    Returns:
        dict with status, video_path (local), and video_uri (GCS)
    """
    from .tools.ffmpeg_mcp import FFmpegMCP
    
    logger.info("=== Processing videos with FFmpeg MCP ===")
    logger.info(f"Videos: {len(video_uris)} files")
    logger.info(f"Narration: {'Yes' if narration_path else 'No'}")
    logger.info(f"Music: {'Yes' if music_path else 'No'}")
    logger.info(f"Volume prompt: {volume_prompt}")
    
    if not video_uris:
        return {"status": "error", "detail": "No video URIs provided"}
    
    try:
        # Download GCS files to local paths if needed
        local_videos = []
        temp_files = []
        
        for video_uri in video_uris:
            if video_uri.startswith("gs://"):
                local_video = download_to_temp(video_uri)
                temp_files.append(local_video)
            else:
                local_video = video_uri
            
            # Validate local file exists
            if not os.path.exists(local_video):
                return {"status": "error", "detail": f"Video file not found: {local_video}"}
            
            local_videos.append(local_video)
        
        # Download narration if needed
        local_narr = None
        if narration_path:
            if narration_path.startswith("gs://"):
                local_narr = download_to_temp(narration_path)
                temp_files.append(local_narr)
            else:
                local_narr = narration_path
            
            if not os.path.exists(local_narr):
                return {"status": "error", "detail": f"Narration file not found: {local_narr}"}
        
        # Download music if needed
        local_music = None
        if music_path:
            if music_path.startswith("gs://"):
                local_music = download_to_temp(music_path)
                temp_files.append(local_music)
            else:
                local_music = music_path
            
            if not os.path.exists(local_music):
                return {"status": "error", "detail": f"Music file not found: {local_music}"}
        
        logger.info(f"Local files ready - Videos: {len(local_videos)}, Narration: {local_narr}, Music: {local_music}")
        
        # Initialize FFmpeg MCP
        ffmpeg_mcp = FFmpegMCP()
        
        # Step 1: Concatenate videos with transitions (if multiple videos)
        if len(local_videos) > 1:
            logger.info("Step 1: Concatenating videos with transitions...")
            concatenated_video = ffmpeg_mcp.concatenate_videos_with_transition(
                local_videos,
                transition_type="fade",  # Could be made configurable
                transition_duration=2,
                transition_offset=5
            )
            temp_files.append(concatenated_video)
        else:
            concatenated_video = local_videos[0]
            logger.info("Step 1: Single video provided, skipping concatenation")
        
        # Step 2: Stitch with audio (narration and/or music)
        if local_narr or local_music:
            logger.info("Step 2: Stitching video with audio...")
            final_video_path = ffmpeg_mcp.stitch_video_with_audio(
                concatenated_video,
                background_music_path=local_music,
                voiceover_path=local_narr,
                prompt=volume_prompt
            )
            temp_files.append(final_video_path)
        else:
            final_video_path = concatenated_video
            logger.info("Step 2: No audio files provided, using video as-is")
        
        # Step 3: Upload final video to GCS
        base_name = f"processed_video_{len(video_uris)}_clips"
        unique_name = f"{base_name}_{uuid.uuid4().hex}.mp4"
        output_gcs_uri = f"gs://{os.getenv('GOOGLE_CLOUD_STORAGE_BUCKET')}/artisan_videos/{unique_name}"
        
        final_gcs_uri = upload_to_gcs(final_video_path, output_gcs_uri, "video/mp4")
        logger.info(f"Final video uploaded to GCS: {final_gcs_uri}")
        
        # Step 4: Clean up temporary files
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    logger.debug(f"Cleaned up temp file: {temp_file}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp file {temp_file}: {e}")
        
        return {
            "status": "success",
            "detail": f"Video processing completed successfully at {final_gcs_uri}",
            "video_path": final_video_path,
            "video_uri": final_gcs_uri
        }
        
    except Exception as e:
        logger.error(f"Failed to process videos with FFmpeg MCP: {e}", exc_info=True)
        return {"status": "error", "detail": f"Video processing failed: {e}"}


# Sub-agent definition:
artisan_video_agent = Agent(
    model=MODEL,
    name="artisan_video_agent",
    description="Generates short-form videos (8-10 seconds) from artisan product images using Google's Veo model in 16:9 aspect ratio.",
    instruction=prompt.ARTISAN_VIDEO_PROMPT,
    output_key="artisan_video_output",
    tools=[generate_artisan_video,
           generate_voiceover,
           generate_background_music,
           process_videos_with_ffmpeg_mcp],
)
