import os
import argparse
from moviepy import VideoFileClip, TextClip, CompositeVideoClip
import whisper
from itertools import cycle
from PIL import Image
import numpy as np

def make_zoom_transform(duration):
    def transform_function(get_frame, t):
        # Calculate the scale factor based on time
        transition_duration = duration * 0.2  # 20% of the total duration
        if t < transition_duration:
            scale = 0.5 + (0.5 * (t / transition_duration))
        else:
            scale = 1.0
            
        # Get the frame
        frame = get_frame(t)
        h, w = frame.shape[:2]
        new_h, new_w = int(h * scale), int(w * scale)
        
        # Convert numpy array to PIL Image for resizing
        pil_img = Image.fromarray(frame)
        resized_img = pil_img.resize((new_w, new_h), Image.LANCZOS)
        resized = np.array(resized_img)
        
        # Create a background frame of the original size
        result = np.zeros((h, w, frame.shape[2]), dtype=frame.dtype)
        
        # Center the resized frame
        y_offset = (h - new_h) // 2
        x_offset = (w - new_w) // 2
        result[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized
        
        return result
    
    return transform_function

def add_captions_to_video(input_video_path, output_path=None):
    """
    Add animated captions to a video file
    
    Args:
        input_video_path (str): Path to input video file from the Reddit video maker
        output_path (str): Path for output video (if None, will use input path + '_captioned')
        temp_audio (str): Path for temporary audio file
    """
    temp_audio = "temp_audio.wav"
    
    if output_path is None:
        # Generate output path based on input path
        base, ext = os.path.splitext(input_video_path)
        output_path = f"{base}_captioned{ext}"

    # Define colors to cycle through
    colors = cycle(['#00BFFF', '#00BFFF', '#00BFFF',
                   '#90EE90', '#90EE90', '#90EE90',
                   '#FFD700', '#FFD700', '#FFD700'])

    video = VideoFileClip(input_video_path)
    
    print("Extracting audio from video...")
    video.audio.write_audiofile(temp_audio)

    print("Loading Whisper model and transcribing audio...")
    model = whisper.load_model("base")
    result = model.transcribe(
        temp_audio,
        language="en",
        word_timestamps=True,
        condition_on_previous_text=False
    )

    os.remove(temp_audio)

    subtitle_clips = []
    font_path = os.path.join("fonts", "Roboto-Black.ttf")

    for segment in result["segments"]:
        for word_info in segment.get("words", []):
            word = word_info["word"].strip()
            start = word_info["start"]
            end = word_info["end"]
            duration = end - start

            if not word or word.isspace():
                continue

            txt_clip = TextClip(
                font=font_path,
                text=word,
                font_size=100,
                size=(video.w, None),
                color=next(colors),
                stroke_color='black',
                stroke_width=6,
                method='caption',
                bg_color=None,
                margin=(40, 40)
            )
            
            txt_clip = txt_clip.transform(make_zoom_transform(duration))
            
            txt_clip = (txt_clip
                       .with_start(start)
                       .with_duration(duration)
                       .with_position(('center', 'center')))
            
            subtitle_clips.append(txt_clip)

    final_video = CompositeVideoClip([video] + subtitle_clips)

    print("Writing output video with captions...")
    final_video.write_videofile(output_path, codec="libx264", audio_codec="aac")

    video.close()
    final_video.close()

def main(args):
    add_captions_to_video(args[0], args[1])

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Add animated captions to a video')
    parser.add_argument('video_file', help='Input video file')
    parser.add_argument('--output_file', default='output_captioned.mp4', help='Output video file (default: output_captioned.mp4)')
    
    args = parser.parse_args()
    
    main([args.video_file, args.output_file])