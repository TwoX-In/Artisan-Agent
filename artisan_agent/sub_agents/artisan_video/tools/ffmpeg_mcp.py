"""
FFmpeg MCP Class

A clean MCP-style class for video processing tasks:
1. Concatenate videos with transitions
2. Stitch video with background music and voiceover based on volume instructions
"""

import subprocess
import tempfile
import re
import json
from typing import List, Dict, Optional
from ....logger import get_logger

logger = get_logger(__name__)


class FFmpegMCP:
    """
    MCP class for FFmpeg video processing operations.
    Handles video concatenation and audio stitching based on natural language prompts.
    """
    
    def __init__(self):
        """Initialize the FFmpeg MCP processor."""
        logger.info("FFmpegMCP initialized")
    
    def get_audio_duration(self, audio_path: str) -> float:
        """
        Get the duration of an audio file in seconds.
        
        Args:
            audio_path: Path to the audio file
            
        Returns:
            Duration in seconds as float
            
        Raises:
            RuntimeError: If unable to get duration
        """
        try:
            cmd = [
                "ffprobe", "-v", "quiet", "-print_format", "json", "-show_format",
                audio_path
            ]
            result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            data = json.loads(result.stdout.decode())
            duration = float(data['format']['duration'])
            logger.debug(f"Audio duration for {audio_path}: {duration} seconds")
            return duration
        except (subprocess.CalledProcessError, KeyError, ValueError) as e:
            logger.error(f"Failed to get audio duration for {audio_path}: {e}")
            # Return a default duration if we can't determine it
            return 30.0

    def get_video_duration(self, video_path: str) -> float:
        """
        Get the duration of a video file in seconds.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            Duration in seconds as float
        """
        try:
            cmd = [
                "ffprobe", "-v", "quiet", "-print_format", "json", "-show_format",
                video_path
            ]
            result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            data = json.loads(result.stdout.decode())
            duration = float(data['format']['duration'])
            logger.debug(f"Video duration for {video_path}: {duration} seconds")
            return duration
        except (subprocess.CalledProcessError, KeyError, ValueError) as e:
            logger.error(f"Failed to get video duration for {video_path}: {e}")
            # Return a default duration if we can't determine it
            return 15.0
    
    def run_ffmpeg_command(self, cmd: List[str], error_msg: str) -> None:
        """
        Execute an FFmpeg command with proper error handling.
        
        Args:
            cmd: FFmpeg command as list of strings
            error_msg: Error message to display if command fails
            
        Raises:
            RuntimeError: If FFmpeg command fails
        """
        logger.info(f"Executing FFmpeg: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.info("FFmpeg command completed successfully")
            if result.stderr:
                logger.debug(f"FFmpeg stderr: {result.stderr.decode(errors='ignore')}")
        except subprocess.CalledProcessError as e:
            error_detail = e.stderr.decode(errors='ignore') if e.stderr else str(e)
            logger.error(f"{error_msg}: {error_detail}")
            raise RuntimeError(f"{error_msg}: {error_detail}")
    
    def concatenate_videos_with_transition(self, video_paths: List[str], 
                                         transition_type: str = "fade",
                                         transition_duration: int = 2,
                                         transition_offset: int = 5) -> str:
        """
        Concatenate multiple videos with smooth transitions between them.
        
        Args:
            video_paths: List of local video file paths to concatenate
            transition_type: Type of transition (fade, wipe, slide, dissolve)
            transition_duration: Duration of each transition in seconds
            transition_offset: Offset for transition start in seconds
            
        Returns:
            Path to the concatenated video file
            
        Raises:
            ValueError: If less than 2 videos provided
            RuntimeError: If FFmpeg processing fails
        """
        if len(video_paths) < 2:
            if len(video_paths) == 1:
                logger.info("Only one video provided, returning as-is")
                return video_paths[0]
            else:
                raise ValueError("At least 1 video path is required")
        
        logger.info(f"=== Concatenating {len(video_paths)} videos with {transition_type} transitions ===")
        for i, path in enumerate(video_paths):
            logger.info(f"  Video {i+1}: {path}")
        
        # Start with the first video
        current_video = video_paths[0]
        
        # Progressively add each subsequent video with transitions
        for i in range(1, len(video_paths)):
            logger.info(f"Adding transition {i}/{len(video_paths)-1}: {current_video} -> {video_paths[i]}")
            
            output_path = tempfile.mktemp(suffix=f"_transition_{i}.mp4")
            
            # Build FFmpeg filter for video and audio crossfade
            filter_complex = (
                f"[0:v][1:v]xfade=transition={transition_type}:duration={transition_duration}:offset={transition_offset}[v];"
                f"[0:a][1:a]acrossfade=d={transition_duration}[a]"
            )
            
            cmd = [
                "ffmpeg", "-y",
                "-i", current_video,
                "-i", video_paths[i],
                "-filter_complex", filter_complex,
                "-map", "[v]",
                "-map", "[a]",
                "-c:a", "aac",
                output_path
            ]
            
            self.run_ffmpeg_command(cmd, f"Failed to apply transition {i}")
            
            # Update current video for next iteration
            current_video = output_path
            logger.info(f"Transition {i} completed: {output_path}")
        
        logger.info(f"=== Video concatenation completed: {current_video} ===")
        return current_video
    
    def stitch_video_with_audio(self, video_path: str, 
                              background_music_path: Optional[str] = None,
                              voiceover_path: Optional[str] = None,
                              prompt: str = "") -> str:
        """
        Stitch video with background music and voiceover based on volume instructions in prompt.
        
        Args:
            video_path: Path to the input video file
            background_music_path: Optional path to background music file
            voiceover_path: Optional path to voiceover audio file
            prompt: Natural language prompt with volume instructions
            
        Returns:
            Path to the final stitched video file
            
        Raises:
            ValueError: If no audio files provided
            RuntimeError: If FFmpeg processing fails
        """
        if not background_music_path and not voiceover_path:
            logger.info("No audio files provided, returning original video")
            return video_path
        
        logger.info("=== Stitching video with audio ===")
        logger.info(f"Video: {video_path}")
        logger.info(f"Background music: {background_music_path or 'None'}")
        logger.info(f"Voiceover: {voiceover_path or 'None'}")
        logger.info(f"Volume prompt: {prompt}")
        
        # Get video duration to limit audio to match
        video_duration = self.get_video_duration(video_path)
        logger.info(f"Video duration: {video_duration:.1f}s - audio will be trimmed to match")
        
        # Parse volume levels from prompt
        volumes = self._parse_volume_from_prompt(prompt)
        logger.info(f"Parsed volumes: {volumes}")
        
        output_path = tempfile.mktemp(suffix="_stitched.mp4")
        
        # Build FFmpeg command based on available audio files
        if background_music_path and voiceover_path:
            # Both background music and voiceover
            # Get original music duration but trim to video duration
            music_duration = self.get_audio_duration(background_music_path)
            effective_duration = min(music_duration, video_duration)  # Use shorter duration
            
            logger.info(f"Music: {music_duration:.1f}s → trimmed to {effective_duration:.1f}s to match video")
            
            # Determine fade duration based on prompt and available time
            if 'dramatic fade' in prompt.lower() or 'long fade' in prompt.lower() or 'slow fade' in prompt.lower():
                fade_duration = min(8.0, effective_duration * 0.4)  # Max 40% of duration
            elif 'quick fade' in prompt.lower() or 'fast fade' in prompt.lower():
                fade_duration = min(2.0, effective_duration * 0.2)  # Max 20% of duration
            else:
                fade_duration = min(5.0, effective_duration * 0.3)  # Max 30% of duration
            
            fade_start = max(0, effective_duration - fade_duration)  # Ensure non-negative
            
            # Apply fade-out and trim music to video duration
            if effective_duration > fade_duration:
                music_filter = f"[1:a]atrim=0:{video_duration},volume={volumes['music']},afade=t=out:st={fade_start}:d={fade_duration}[music_audio]"
                logger.info(f"Trimming music to {video_duration:.1f}s with fade-out: start={fade_start:.1f}s, duration={fade_duration:.1f}s")
            else:
                music_filter = f"[1:a]atrim=0:{video_duration},volume={volumes['music']}[music_audio]"
                logger.info(f"Trimming music to {video_duration:.1f}s (too short for fade-out)")
            
            filter_complex = (
                f"[0:a]volume={volumes['video']}[video_audio];"
                f"{music_filter};"
                f"[2:a]atrim=0:{video_duration},volume={volumes['voiceover']}[voice_audio];"
                f"[video_audio][music_audio][voice_audio]amix=inputs=3:duration=first[a]"
            )
            
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-i", background_music_path,
                "-i", voiceover_path,
                "-filter_complex", filter_complex,
                "-map", "0:v",
                "-map", "[a]",
                "-c:v", "copy",
                "-c:a", "aac",
                output_path
            ]
            
        elif background_music_path:
            # Only background music
            # Get original music duration but trim to video duration
            music_duration = self.get_audio_duration(background_music_path)
            effective_duration = min(music_duration, video_duration)  # Use shorter duration
            
            logger.info(f"Music: {music_duration:.1f}s → trimmed to {effective_duration:.1f}s to match video")
            
            # Determine fade duration based on available time
            fade_duration = min(5.0, effective_duration * 0.3)  # Max 30% of duration
            fade_start = max(0, effective_duration - fade_duration)  # Ensure non-negative
            
            # Apply fade-out and trim music to video duration
            if effective_duration > fade_duration:
                music_filter = f"[1:a]atrim=0:{video_duration},volume={volumes['music']},afade=t=out:st={fade_start}:d={fade_duration}[music_audio]"
                logger.info(f"Trimming music to {video_duration:.1f}s with fade-out: start={fade_start:.1f}s, duration={fade_duration:.1f}s")
            else:
                music_filter = f"[1:a]atrim=0:{video_duration},volume={volumes['music']}[music_audio]"
                logger.info(f"Trimming music to {video_duration:.1f}s (too short for fade-out)")
            
            filter_complex = (
                f"[0:a]volume={volumes['video']}[video_audio];"
                f"{music_filter};"
                f"[video_audio][music_audio]amix=inputs=2:duration=first[a]"
            )
            
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-i", background_music_path,
                "-filter_complex", filter_complex,
                "-map", "0:v",
                "-map", "[a]",
                "-c:v", "copy",
                "-c:a", "aac",
                output_path
            ]
            
        elif voiceover_path:
            # Only voiceover
            logger.info(f"Trimming voiceover to {video_duration:.1f}s to match video")
            filter_complex = (
                f"[0:a]volume={volumes['video']}[video_audio];"
                f"[1:a]atrim=0:{video_duration},volume={volumes['voiceover']}[voice_audio];"
                f"[video_audio][voice_audio]amix=inputs=2:duration=first[a]"
            )
            
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-i", voiceover_path,
                "-filter_complex", filter_complex,
                "-map", "0:v",
                "-map", "[a]",
                "-c:v", "copy",
                "-c:a", "aac",
                "-shortest",
                output_path
            ]
        
        self.run_ffmpeg_command(cmd, "Failed to stitch video with audio")
        logger.info(f"=== Audio stitching completed: {output_path} ===")
        return output_path
    
    def _parse_volume_from_prompt(self, prompt: str) -> Dict[str, float]:
        """
        Parse volume levels from natural language prompt.
        
        Args:
            prompt: Natural language prompt containing volume instructions
            
        Returns:
            Dict with volume levels for video, music, and voiceover
        """
        prompt_lower = prompt.lower()
        
        # Default volumes
        volumes = {
            'video': 0.3,      # Original video audio (usually low for background)
            'music': 0.4,      # Background music (increased from 0.2 to be more audible)
            'voiceover': 1.0   # Voiceover (usually prominent)
        }
        
        # Parse music volume
        if 'loud music' in prompt_lower or 'high music' in prompt_lower:
            volumes['music'] = 0.6
        elif 'quiet music' in prompt_lower or 'soft music' in prompt_lower or 'low music' in prompt_lower:
            volumes['music'] = 0.2  # Increased from 0.1 to be more audible
        elif 'medium music' in prompt_lower or 'moderate music' in prompt_lower:
            volumes['music'] = 0.4
        elif 'no music' in prompt_lower or 'mute music' in prompt_lower:
            volumes['music'] = 0.0
        
        # Note: Fade out is automatically applied to background music
        if 'fade out' in prompt_lower or 'fade music' in prompt_lower:
            # Fade out is already implemented in the filter - this is just for logging
            logger.info("Fade out requested for background music (automatically applied)")
        
        # Parse voiceover volume
        if 'loud voice' in prompt_lower or 'clear voice' in prompt_lower or 'prominent voice' in prompt_lower:
            volumes['voiceover'] = 1.2
        elif 'quiet voice' in prompt_lower or 'soft voice' in prompt_lower or 'low voice' in prompt_lower:
            volumes['voiceover'] = 0.7
        elif 'medium voice' in prompt_lower or 'moderate voice' in prompt_lower:
            volumes['voiceover'] = 1.0
        elif 'no voice' in prompt_lower or 'mute voice' in prompt_lower:
            volumes['voiceover'] = 0.0
        
        # Parse video audio volume
        if 'loud video' in prompt_lower or 'keep video audio' in prompt_lower:
            volumes['video'] = 0.8
        elif 'quiet video' in prompt_lower or 'mute video' in prompt_lower or 'no video audio' in prompt_lower:
            volumes['video'] = 0.0
        elif 'medium video' in prompt_lower:
            volumes['video'] = 0.5
        
        # Parse specific numeric values (e.g., "music at 20%", "voice at 0.8")
        music_match = re.search(r'music.*?(\d+)%', prompt_lower)
        if music_match:
            volumes['music'] = float(music_match.group(1)) / 100
        
        voice_match = re.search(r'voice.*?(\d+)%', prompt_lower)
        if voice_match:
            volumes['voiceover'] = float(voice_match.group(1)) / 100
        
        video_match = re.search(r'video.*?(\d+)%', prompt_lower)
        if video_match:
            volumes['video'] = float(video_match.group(1)) / 100
        
        # Parse decimal values (e.g., "music at 0.2", "voice at 1.0")
        music_decimal = re.search(r'music.*?(\d*\.\d+)', prompt_lower)
        if music_decimal:
            volumes['music'] = float(music_decimal.group(1))
        
        voice_decimal = re.search(r'voice.*?(\d*\.\d+)', prompt_lower)
        if voice_decimal:
            volumes['voiceover'] = float(voice_decimal.group(1))
        
        video_decimal = re.search(r'video.*?(\d*\.\d+)', prompt_lower)
        if video_decimal:
            volumes['video'] = float(video_decimal.group(1))
        
        return volumes
