import os
import requests
import base64
import uuid
from google.auth import default
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.cloud import storage
from ....logger import get_logger

logger = get_logger(__name__)

class LyriaClient:
    def __init__(self, model: str = "lyria-002"):
        self.model = model
        # Use "us-central1" as the location for Lyria model
        self.location = os.getenv("GOOGLE_CLOUD_LOCATION_LYRIA", "us-central1")
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        self.bucket = os.getenv("GOOGLE_CLOUD_STORAGE_BUCKET")

        if not self.project_id:
            raise ValueError("GOOGLE_CLOUD_PROJECT environment variable is required")

        # Build the endpoint URL (matching official docs format)
        self.endpoint = (
            f"https://{self.location}-aiplatform.googleapis.com/v1/"
            f"projects/{self.project_id}/locations/{self.location}/"
            f"publishers/google/models/{self.model}:predict"
        )

        self._credentials = None
        self._access_token = None

        logger.info(f"LyriaClient initialized - Model: {self.model}, Endpoint: {self.endpoint}")

    def _get_access_token(self) -> str:
        scopes = ['https://www.googleapis.com/auth/cloud-platform']

        if not self._credentials:
            service_account_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_KEY')
            if service_account_json:
                import json
                try:
                    info = json.loads(service_account_json)
                    self._credentials = service_account.Credentials.from_service_account_info(info, scopes=scopes)
                except Exception as e:
                    logger.warning(f"Failed to parse service account JSON: {e}")

            if not self._credentials:
                sa_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
                if sa_path and os.path.exists(sa_path):
                    self._credentials = service_account.Credentials.from_service_account_file(sa_path, scopes=scopes)

            if not self._credentials:
                self._credentials, _ = default(scopes=scopes)

        if not self._credentials.valid or not self._access_token:
            self._credentials.refresh(Request())
            self._access_token = self._credentials.token

        return self._access_token

    def generate_music(self, prompt: str, seed: int = None, sample_count: int = None, negative_prompt: str = None) -> bytes:
        if not prompt:
            raise ValueError("prompt is required")

        # Build instance according to official docs
        instance = {"prompt": prompt}
        if negative_prompt:
            instance["negative_prompt"] = negative_prompt
        if seed is not None:
            instance["seed"] = seed

        # Build payload according to official docs format
        payload = {
            "instances": [instance],
            "parameters": {}
        }
        
        # Add sample_count to parameters if specified (use either seed or sample_count)
        if sample_count is not None:
            if seed is not None:
                raise ValueError("Cannot use both seed and sample_count per Lyria docs")
            payload["parameters"]["sample_count"] = sample_count

        headers = {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json"
        }

        logger.debug(f"Requesting Lyria with payload: {payload} to endpoint {self.endpoint}")
        response = requests.post(self.endpoint, json=payload, headers=headers, timeout=120)
        try:
            response.raise_for_status()
        except requests.HTTPError as http_err:
            logger.error(f"Lyria API returned HTTP error: {http_err}, body: {response.text}")
            raise Exception(f"Lyria API request failed: {http_err}, response: {response.text}")

        result = response.json()
        logger.debug(f"Lyria response JSON: {result}")

        if "predictions" in result and result["predictions"]:
            pred = result["predictions"][0]
            # Check for both possible field names
            if "audioContent" in pred:
                audio_content = base64.b64decode(pred["audioContent"])
                return audio_content
            elif "bytesBase64Encoded" in pred:
                audio_content = base64.b64decode(pred["bytesBase64Encoded"])
                return audio_content
            else:
                raise Exception(f"Audio content missing in prediction. Available keys: {list(pred.keys())}")
        else:
            raise Exception(f"No predictions returned: {result}")

    def generate_music_file(self, prompt: str, output_path: str = None, seed: int = None) -> str:
        """Generate music and save to a local file."""
        if not output_path:
            unique_name = f"music_{uuid.uuid4().hex}.wav"
            output_path = f"/tmp/{unique_name}"
        
        logger.info(f"Generating music file: {output_path}")
        audio_content = self.generate_music(prompt, seed=seed)
        
        with open(output_path, "wb") as f:
            f.write(audio_content)
        
        logger.info(f"Music saved to: {output_path}")
        return output_path

    def generate_music_with_gcs(self, prompt: str, product_name: str, seed: int = None) -> dict:
        """Generate music, save locally, and upload to GCS."""
        try:
            # Generate unique filename
            base_name = os.path.splitext(os.path.basename(product_name))[0]
            unique_name = f"{base_name}_music_{uuid.uuid4().hex}.wav"
            local_path = f"/tmp/{unique_name}"
            
            # Generate music file
            self.generate_music_file(prompt, local_path, seed=seed)
            
            # Upload to GCS
            if self.bucket:
                gcs_path = f"artisan_videos/{unique_name}"
                gcs_uri = f"gs://{self.bucket}/{gcs_path}"
                
                client = storage.Client()
                bucket = client.bucket(self.bucket)
                blob = bucket.blob(gcs_path)
                blob.upload_from_filename(local_path, content_type="audio/wav")
                
                logger.info(f"Music uploaded to GCS: {gcs_uri}")
                
                # Clean up local temp file after successful upload
                try:
                    if os.path.exists(local_path):
                        os.remove(local_path)
                        logger.debug(f"Cleaned up temp music file: {local_path}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temp music file {local_path}: {e}")
                
                return {
                    "status": "success",
                    "detail": "Background music generated successfully",
                    "music_path": gcs_uri,  # Return GCS URI instead of local path
                    "audio_gcs_uri": gcs_uri
                }
            else:
                logger.warning("No GCS bucket configured, returning local path only")
                return {
                    "status": "success",
                    "detail": "Background music generated successfully (local only)",
                    "music_path": local_path,
                    "audio_gcs_uri": None
                }
                
        except Exception as e:
            logger.error(f"Music generation with GCS failed: {e}", exc_info=True)
            return {
                "status": "error",
                "detail": f"Music generation failed: {e}"
            }
