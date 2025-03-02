# Video Caption Generator

A Python script that automatically adds animated captions to videos using speech recognition, with extensive customization options.

## Features

- **Automatic Captioning**
  - Uses OpenAI's Whisper model for speech-to-text transcription
  - Word-by-word or multi-word animated captions
  - Customizable zoom animation effects

- **Styling Options**
  - Color cycling for captions
  - Configurable font, size, and positioning
  - Text stroke and background options
  - Highlight individual words

- **Advanced Video Editing**
  - Optional intro sound
  - Video overlay support
  - Flexible caption placement

## Prerequisites

- Python 3.8 or higher
- FFmpeg installed on your system
- GPU recommended for faster processing (optional)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd video-caption-generator
```

2. Install dependencies:
```bash
pip install moviepy whisper PyYAML requests fonttools pillow
```

## Font Management with `fontify.py`

The `fontify.py` script provides an easy way to download fonts from Google Fonts:

```bash
# Download a specific font
python fontify.py "Open Sans"
# Or
python fontify.py "Roboto Black"
```

This script will:
- Query the Google Fonts API
- Download the font file
- Save it in a `./fonts` directory

## Configuration

Configuration is managed through a `config.toml` file with numerous options:

### Caption Display
- `number_of_words`: Number of words to display at once
- `font`: Font filename
- `font_size`: Text size in pixels
- `position`: Screen position (top/center/bottom)
- `text_align`: Text alignment
- `text_colors`: Color cycling for captions
- `stroke_color` and `stroke_width`: Text outline styling
- `bg_color`: Background color or transparency

### Advanced Options
- `transition`: Zoom animation toggle
- `highlight`: Highlight current word
- `has_intro_sound`: Add background audio
- `overlay`: Overlay another video

## Usage

### Command Line
```bash
# Basic usage
python caption.py input_video.mp4

# Specify output and configuration
python caption.py input_video.mp4 --output_file captioned_video.mp4 --config custom_config.toml
```

### Programmatic Usage
```python
from caption import add_captions_to_video

add_captions_to_video(
    "input_video.mp4", 
    output_path="output_video.mp4", 
    config_path="config.toml"
)
```

## Video Silence Trimmer

Included `silence_trimmer.py` allows removing silent segments from videos:

```bash
python silence_trimmer.py input_video.mp4
```

## Troubleshooting

1. **Font Issues**
   - Use `fontify.py` to download missing fonts
   - Ensure fonts are in the `./fonts` directory

2. **Performance**
   - Use smaller Whisper models for faster processing
   - Reduce video resolution if memory is limited

3. **Dependencies**
   - Ensure all required libraries are installed
   - Check FFmpeg installation

## Customization Tips

- Experiment with `config.toml` settings
- Try different fonts using `fontify.py`
- Adjust Whisper model for accuracy vs. speed

## Technologies Used

- MoviePy: Video processing
- Whisper: Speech recognition
- PIL (Pillow): Image manipulation
- TOML: Configuration management

## License

- Apache License 2.0 (for Roboto Fonts)
- MIT License for the script

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a pull request

## Credits

- OpenAI (Whisper)
- Google Fonts
- MoviePy Developers