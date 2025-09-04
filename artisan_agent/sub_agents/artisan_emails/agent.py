"""Artisan email generation agent using custom conversational model endpoint"""

import json
import os
import requests
from typing import Dict, Any
from dotenv import load_dotenv
from google.adk import Agent
from google.adk.tools import ToolContext
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from ...logger import get_logger

from . import prompt

# Initialize logger
logger = get_logger(__name__)

# Load environment variables
load_dotenv()

# Custom model endpoint configuration from environment variables
EMAIL_MODEL_ENDPOINT = os.getenv("EMAIL_MODEL_ENDPOINT")
SERVICE_ACCOUNT_FILE = os.getenv("EMAIL_SERVICE_ACCOUNT_FILE")  # Specific env var for email model
PROJECT_ID = os.getenv("EMAIL_MODEL_PROJECT")  # Email model project ID

# Fallback model for the Agent framework
MODEL = "gemini-2.5-pro"

def get_email_model_credentials():
    """Get credentials from environment-specified service account file for email model"""
    if not SERVICE_ACCOUNT_FILE:
        raise ValueError("EMAIL_SERVICE_ACCOUNT_FILE environment variable is required")
    if not PROJECT_ID:
        raise ValueError("EMAIL_MODEL_PROJECT environment variable is required")
    
    # Determine the full path to credentials file
    if os.path.isabs(SERVICE_ACCOUNT_FILE):
        credentials_path = SERVICE_ACCOUNT_FILE
    else:
        credentials_path = os.path.join(os.path.dirname(__file__), "../../../", SERVICE_ACCOUNT_FILE)
    
    # Check if file exists
    if not os.path.exists(credentials_path):
        raise FileNotFoundError(f"Email service account file not found: {credentials_path}")
    
    # Load credentials from file
    try:
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
        logger.info(f"✅ Loaded email service account from: {credentials_path} (project: {PROJECT_ID})")
        return credentials
    except Exception as e:
        raise ValueError(f"Failed to load email credentials from {credentials_path}: {e}")


async def generate_email_content(
    product_name: str,
    product_description: str,
    email_type: str = "promotional",
    target_audience: str = "general customers",
    brand_tone: str = "luxury",
    tool_context: ToolContext = None,
) -> Dict[str, Any]:
    """
    Generate artisan email content using the custom conversational model endpoint.
    
    Args:
        product_name: Name of the artisan product
        product_description: Detailed description of the product
        email_type: Type of email (promotional, newsletter, etc.)
        target_audience: Description of target audience
        brand_tone: Desired tone (luxury, casual, warm, etc.)
        tool_context: ADK tool context for saving artifacts
        
    Returns:
        Dict containing generated email content
    """
    
    logger.info(f"Generating email content for product: {product_name}")
    logger.info(f"Email type: {email_type}, Tone: {brand_tone}, Audience: {target_audience}")
    
    try:
        # Get Google Cloud credentials
        credentials = get_email_model_credentials()
        if not credentials.valid:
            credentials.refresh(Request())
        
        # Format the request in the conversational format your model expects
        user_prompt = f"Product: {product_name}\nDescription: {product_description}\nTone: {brand_tone}\nTask: Write a marketing email."
        
        # Create the conversational format request
        request_payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": user_prompt
                        }
                    ]
                }
            ]
        }
        
        # Set up headers with authentication
        headers = {
            "Authorization": f"Bearer {credentials.token}",
            "Content-Type": "application/json"
        }
        
        logger.info("Calling custom email model endpoint")
        logger.debug(f"Request payload: {json.dumps(request_payload, indent=2)}")
        
        # Make request to custom model endpoint
        response = requests.post(
            EMAIL_MODEL_ENDPOINT,
            headers=headers,
            json=request_payload,
            timeout=60
        )
        
        if response.status_code != 200:
            error_msg = f"Custom model request failed with status {response.status_code}: {response.text}"
            logger.error(error_msg)
            return {
                "status": "error",
                "message": error_msg
            }
        
        # Parse response from custom model
        response_data = response.json()
        logger.info("Successfully received response from custom model")
        logger.debug(f"Response data: {json.dumps(response_data, indent=2)}")
        
        # Extract the generated content based on your model's response format
        if "parts" in response_data and len(response_data["parts"]) > 0:
            # Direct response format: {"role": "model", "parts": [{"text": "..."}]}
            generated_text = response_data["parts"][0]["text"]
            logger.info(f"Generated email content: {generated_text[:100]}...")
        else:
            # Fallback if response structure is different
            generated_text = str(response_data)
        
        # Parse the generated email content
        # Based on your example: "Subject: ... \n\nHi [Name],\n..."
        email_parts = generated_text.split('\n\n', 1)
        
        if len(email_parts) >= 2 and email_parts[0].startswith('Subject:'):
            subject_line = email_parts[0].replace('Subject:', '').strip()
            email_body = email_parts[1].strip()
        else:
            # If format is different, use the whole response as body
            subject_line = "Discover Artisan Excellence"
            email_body = generated_text
        
        email_content = {
            "subject_line": subject_line,
            "email_body": email_body,
            "product_name": product_name,
            "tone": brand_tone,
            "raw_response": generated_text
        }
        
        # Save the generated email as an artifact if tool_context is provided
        if tool_context:
            email_html = f"""
            <html>
            <head><title>Artisan Email - {product_name}</title></head>
            <body>
                <h1>Email Marketing Content</h1>
                
                <div style="background-color: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 5px;">
                    <h2>Product Details</h2>
                    <p><strong>Product:</strong> {product_name}</p>
                    <p><strong>Description:</strong> {product_description}</p>
                    <p><strong>Tone:</strong> {brand_tone}</p>
                    <p><strong>Audience:</strong> {target_audience}</p>
                </div>
                
                <div style="background-color: #e8f5e8; padding: 15px; margin: 10px 0; border-radius: 5px;">
                    <h2>Generated Email Content</h2>
                    <p><strong>Subject:</strong> {email_content['subject_line']}</p>
                    <div style="border: 1px solid #ddd; padding: 15px; margin: 10px 0; background-color: white;">
                        <pre style="white-space: pre-wrap; font-family: Arial, sans-serif;">{email_content['email_body']}</pre>
                    </div>
                </div>
                
                <div style="background-color: #fff3e0; padding: 15px; margin: 10px 0; border-radius: 5px;">
                    <h2>Raw Model Response</h2>
                    <pre style="white-space: pre-wrap; font-size: 12px;">{email_content['raw_response']}</pre>
                </div>
            </body>
            </html>
            """
            
            await tool_context.save_artifact(
                f"artisan_email_{product_name.replace(' ', '_').lower()}.html",
                email_html.encode('utf-8'),
                mime_type="text/html"
            )
            
            logger.info("Email content saved as artifact")
        
        logger.info("Email generation completed successfully")
        return {
            "status": "success",
            "email_content": email_content,
            "message": "Email content generated successfully using custom conversational model"
        }
        
    except Exception as e:
        error_msg = f"Error generating email content: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "status": "error",
            "message": error_msg
        }


# Define the artisan email agent
artisan_email_agent = Agent(
    model=MODEL,
    name="artisan_email_agent",
    description=(
        "An agent that generates compelling email marketing content for artisan businesses "
        "using a custom conversational model endpoint trained specifically for email generation."
    ),
    instruction=prompt.ARTISAN_EMAIL_PROMPT,
    output_key="artisan_email_output",
    tools=[generate_email_content],
)
