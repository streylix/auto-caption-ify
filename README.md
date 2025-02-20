# Video Caption Generator

A Python script that automatically adds animated captions to videos using speech recognition. The captions appear with a zoom animation effect and cycle through different colors for better visibility.

## Features

- Automatic speech-to-text transcription using OpenAI's Whisper model
- Word-by-word animated captions with zoom effects
- Color cycling for better visibility (alternates between light blue, light green, and gold)
- Centered text positioning with black outline for readability
- Support for custom input and output paths

## Prerequisites

- Python 3.8 or higher
- FFmpeg installed on your system (required for video processing)

## Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd video-caption-generator
```

2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

3. Download the Roboto-Black font and place it in a `fonts` directory:
```bash
mkdir fonts
# Place Roboto-Black.ttf in the fonts directory
```

## Usage

### Basic Usage

```bash
python caption_generator.py input_video.mp4
```

This will create a captioned video with the default output name `output_captioned.mp4`.

### Specifying Output File

```bash
python caption_generator.py input_video.mp4 --output_file custom_output.mp4
```

### Function Usage in Code

You can also import and use the captioning function in your own Python code:

```python
from caption_generator import add_captions_to_video

add_captions_to_video("input_video.mp4", "output_video.mp4")
```

## Configuration

The script includes several hardcoded settings that you can modify in the code:

- Font size: Currently set to 100
- Text colors: Cycles through '#00BFFF' (light blue), '#90EE90' (light green), and '#FFD700' (gold)
- Stroke width: Set to 6 pixels
- Text margin: Set to 40 pixels
- Zoom animation duration: 20% of each word's duration

## Technical Details

The script works by:
1. Extracting audio from the input video
2. Using Whisper to transcribe the audio with word-level timestamps
3. Creating animated text clips for each word
4. Applying a zoom transform effect to each word
5. Compositing all clips together with the original video
6. Saving the final video with the original audio

## Limitations

- Processing time depends on video length and system capabilities
- Requires sufficient disk space for temporary files
- Whisper model accuracy may vary based on audio quality
- Memory usage scales with video resolution and length

## Troubleshooting

Common issues and solutions:

1. **FFmpeg not found error**:
   - Ensure FFmpeg is installed on your system and accessible in your PATH

2. **Font not found error**:
   - Make sure Roboto-Black.ttf is present in the `fonts` directory

3. **Memory errors**:
   - Try processing shorter video segments
   - Reduce video resolution before processing

## License

Roboto Fonts are licensed under Apache License V2

## Credits

- Uses OpenAI's Whisper model for speech recognition
- MoviePy for video processing
- Roboto font by Google Fonts