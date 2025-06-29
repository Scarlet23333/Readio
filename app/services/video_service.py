from boto3 import Session
from botocore.client import Config
import time
from app.config import settings
import os
import tempfile
from typing import Dict, Optional
from app.services.llama4_service import summarize_video_with_frames
from app.services.audio_service import generate_audio
from app.utils.s3_utils import find_latest_video_key, upload_and_get_url
from app.utils.extract_video_frames import extract_frames

class VideoService:
    """Service for extracting text from video using Llama API and generating audio."""
    
    def __init__(self):
        self.perspectives = {
            "educational": "Academic and informative tone",
            "entertaining": "Engaging and conversational tone", 
            "professional": "Business and formal tone",
            "casual": "Relaxed and friendly tone",
            "technical": "Detailed and technical explanations"
        }
        self.session = Session(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )

    def generate_video_content(self, script: str) -> str:
        bedrock_client = self.session.client("bedrock-runtime")
        s3 = self.session.client("s3", config=Config(signature_version='s3v4'))

        try:
            response = bedrock_client.start_async_invoke(
                modelId=settings.BEDROCK_MODEL_ID,
                modelInput={
                    "prompt": script,
                    "aspect_ratio": "16:9",
                    "loop": False,
                    "duration": "9s",
                    "resolution": "720p"
                },
                outputDataConfig={
                    's3OutputDataConfig': {
                        's3Uri': f"s3://{settings.S3_BUCKET_NAME}/"
                    }
                }
            )

            invocation_arn = response['invocationArn']

            while True:
                async_invoke = bedrock_client.get_async_invoke(
                    invocationArn=invocation_arn
                )
                if async_invoke.get('status') != 'InProgress':
                    break
                time.sleep(5)

            s3_key = find_latest_video_key(settings.S3_BUCKET_NAME)
            video_url = s3.generate_presigned_url(
                ClientMethod='get_object',
                Params={'Bucket': settings.S3_BUCKET_NAME, 'Key': s3_key},
                ExpiresIn=3600
            )
            if video_url:
                return video_url
            else:
                return "Error: No video URL returned."
        except Exception as e:
            return f"Error generating video: {str(e)}"

    def process_video_to_audio(self, video_path, perspective: Optional[str] = None) -> Dict:
        """Extract text from video file and generate audio."""            
        dict = extract_frames(video_path)
        frames, duration = dict["frames"], dict["duration"]
        frame_urls = upload_and_get_url(frames, settings.S3_BUCKET_NAME, settings.AWS_REGION)

        script = summarize_video_with_frames(frame_urls, duration, perspective)
        audio_url = generate_audio(script)
        
        return {
            "success": True,
            # "text": script,
            "audio_url": audio_url,
        }
        
