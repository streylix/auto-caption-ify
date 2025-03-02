import sys
import os
import argparse
import shutil
import requests
import subprocess
import tempfile
from urllib.parse import quote
import zipfile
from io import BytesIO
from moviepy import VideoFileClip, TextClip, CompositeVideoClip, AudioFileClip, CompositeAudioClip, ImageClip
import whisper
from itertools import cycle
from PIL import Image, ImageDraw, ImageFont
from fontify import download_font
import numpy as np

# For font handling
import fs
from fs.copy import copy_file
import fs.errors

# Try to import TOML library
try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # Third-party for older Python
    except ImportError:
        print("Warning: Neither tomllib nor tomli found. Please install tomli: pip install tomli")
        exit(1)

def convert_woff_to_ttf(woff_path, output_path=None):
    """
    Convert a WOFF/WOFF2 font file to TTF format using fontTools
    
    Args:
        woff_path (str): Path to the WOFF file
        output_path (str, optional): Path for the output TTF file. If None, uses the same name with .ttf extension
        
    Returns:
        str: Path to the converted TTF file, or None if conversion failed
    """
    if output_path is None:
        output_path = os.path.splitext(woff_path)[0] + ".ttf"
    
    try:
        # Try to install fonttools if not available
        try:
            from fontTools import ttLib
        except ImportError:
            print("Installing fontTools for font conversion...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "fonttools"])
            from fontTools import ttLib

        # Open the WOFF file
        font = ttLib.TTFont(woff_path)
        
        # Save as TTF
        font.save(output_path)
        print(f"Converted {woff_path} to {output_path}")
        return output_path
    except Exception as e:
        print(f"Error converting WOFF to TTF: {e}")
        return None

def load_font_with_fallback(font_path, size=100):
    """
    Load a font with proper fallbacks in case the font fails or doesn't support characters
    
    Args:
        font_path (str): Path to the primary font to try
        size (int): Font size
        
    Returns:
        PIL.ImageFont: A usable font
    """
    # Try the specified font first
    try:
        font = ImageFont.truetype(font_path, size)
        
        # Test if the font can render basic Latin characters
        test_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
        for char in test_chars:
            try:
                if hasattr(font, 'getbbox') and font.getbbox(char) is None:
                    raise Exception(f"Font doesn't properly support basic character '{char}'")
            except:
                # Some older PIL versions might not have getbbox
                pass
        
        return font
    except Exception as e:
        print(f"Error loading font {font_path}: {e}")
        
        # Try system fonts as fallback
        fallback_fonts = [
            # Common system fonts with good Unicode coverage
            "DejaVuSans.ttf",
            "Arial.ttf",
            "Roboto-Regular.ttf",
            "NotoSans-Regular.ttf",
            "OpenSans-Regular.ttf"
        ]
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        fonts_dir = os.path.join(script_dir, "fonts")
        
        # Try each fallback font
        for fallback in fallback_fonts:
            try:
                fallback_path = os.path.join(fonts_dir, fallback)
                if os.path.exists(fallback_path):
                    print(f"Trying fallback font: {fallback}")
                    return ImageFont.truetype(fallback_path, size)
            except Exception:
                continue
        
        # Try standard system font locations
        system_locations = [
            # Linux
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            # macOS
            "/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            # Windows
            "C:\\Windows\\Fonts\\arial.ttf"
        ]
        
        for loc in system_locations:
            try:
                if os.path.exists(loc):
                    print(f"Using system font: {loc}")
                    return ImageFont.truetype(loc, size)
            except Exception:
                continue
        
        # Last resort - use default font
        print("Using PIL default font as last resort")
        return ImageFont.load_default()

def create_highlighted_word_clip(word_buffer, current_index, font_path, video_width, config):
    """
    Create a clip with the current word highlighted
    
    Args:
        word_buffer (list): List of words to display
        current_index (int): Index of the current word to highlight
        font_path (str): Path to the font
        video_width (int): Width of the video
        config (dict): Configuration dictionary
        
    Returns:
        ImageClip: A clip with the current word highlighted
    """
    # Create a blank image with PIL
    from PIL import Image, ImageDraw, ImageFont
    
    # Get configuration values
    font_size = config["font_size"]
    highlight_color = config["highlight_color"]
    stroke_color = config["stroke_color"]  
    stroke_width = config["stroke_width"]
    bg_color = config["bg_color"]
    margin = tuple(config["margin"])
    text_align = config["text_align"]
    
    # Load the font with fallback mechanism
    font = load_font_with_fallback(font_path, font_size)
    
    # Debug: Check if all words can be rendered with this font
    for word in word_buffer:
        for char in word:
            try:
                if hasattr(font, 'getbbox') and font.getbbox(char) is None:
                    print(f"Warning: Character '{char}' (Unicode {ord(char)}) not supported in font")
            except:
                # Some older PIL versions might not have getbbox
                pass
    
    # Calculate text size for layout
    text = " ".join(word_buffer)
    text_width, text_height = 0, 0
    
    # Need to measure each word
    word_positions = []
    current_x = 0
    
    for i, word in enumerate(word_buffer):
        # Get the size of this word
        try:
            # Use getbbox for newer Pillow versions
            bbox = font.getbbox(word)
            if bbox:
                word_width, word_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
            else:
                # Fallback measurement
                word_width, word_height = font.getsize(word) if hasattr(font, 'getsize') else (100, 100)
        except Exception as e:
            print(f"Error measuring text: {e}")
            word_width, word_height = 100 * len(word), 100  # Rough estimate
        
        # Add some padding
        word_width += 10
        
        # Update text dimensions
        text_width += word_width
        text_height = max(text_height, word_height)
        
        # Store word position
        word_positions.append((current_x, word))
        current_x += word_width
    
    # Create image with proper size (add padding)
    padding = 40
    img_width = text_width + (padding * 2)
    img_height = text_height + (padding * 2)
    
    # Create transparent image
    img = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Calculate center position
    center_x = (img_width - text_width) // 2
    center_y = (img_height - text_height) // 2
    
    # Draw each word
    for i, (x_offset, word) in enumerate(word_positions):
        x = center_x + x_offset
        y = center_y
        
        # Use highlight color for current word, white for others
        color = highlight_color if i == current_index else "#FFFFFF"
        
        # Draw text with black outline
        # Outline
        shadow_offset = 3
        for dx in [-shadow_offset, 0, shadow_offset]:
            for dy in [-shadow_offset, 0, shadow_offset]:
                if dx != 0 or dy != 0:  # Skip the center position
                    draw.text((x + dx, y + dy), word, font=font, fill="#000000")
        
        # Main text
        draw.text((x, y), word, font=font, fill=color)
    
    # Convert PIL image to numpy array for MoviePy
    img_array = np.array(img)
    
    # Create ImageClip from the image array
    clip = ImageClip(img_array)
    
    # Set size to fit video width
    if img_width > video_width:
        clip = clip.resized(width=video_width)
    
    return clip

def make_zoom_transform(duration, enabled=True):
    """
    Create a zoom transform function for animations.
    Returns original frame if transitions are disabled.
    
    Args:
        duration (float): Duration of the transition
        enabled (bool): Whether the transition is enabled
        
    Returns:
        function: Transform function for MoviePy
    """
    def transform_function(get_frame, t):
        # If transitions are disabled, just return the frame
        if not enabled:
            return get_frame(t)
            
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

def ensure_font_exists(font_name):
    """
    Check if the specified font exists in the fonts directory.
    If not, attempt to find it in the system or download it.
    
    Args:
        font_name (str): Name of the font file (e.g., "Roboto-Black.ttf")
        
    Returns:
        str: Path to the font file
    """
    # Ensure fonts directory exists
    script_dir = os.path.dirname(os.path.abspath(__file__))
    fonts_dir = os.path.join(script_dir, "fonts")
    os.makedirs(fonts_dir, exist_ok=True)
    
    # Check if font_name contains extension, if not add .ttf
    if not font_name.lower().endswith(('.ttf', '.otf')):
        font_name = f"{font_name}.ttf"
    
    font_path = os.path.join(fonts_dir, font_name)
    
    # If font already exists, return its path
    if os.path.exists(font_path):
        print(f"Font {font_name} found in local directory.")
        return font_path
    
    print(f"Font {font_name} not found locally. Searching in system...")
    
    # Map of proprietary fonts to free alternatives
    alternatives = {
        "arial": "DejaVuSans.ttf",
        "arial.ttf": "DejaVuSans.ttf",
        "helvetica": "DejaVuSans.ttf",
        "helvetica.ttf": "DejaVuSans.ttf",
        "times": "DejaVuSerif.ttf",
        "times.ttf": "DejaVuSerif.ttf",
        "times new roman": "DejaVuSerif.ttf",
        "timesnewroman.ttf": "DejaVuSerif.ttf",
        "courier": "DejaVuSansMono.ttf",
        "courier.ttf": "DejaVuSansMono.ttf",
        "courier new": "DejaVuSansMono.ttf",
        "couriernew.ttf": "DejaVuSansMono.ttf",
    }
    
    # Try to find in system fonts using fs library
    system_font_locations = [
        # Linux
        "/usr/share/fonts",
        "/usr/local/share/fonts",
        "~/.local/share/fonts",
        # macOS
        "/Library/Fonts",
        "/System/Library/Fonts",
        # Windows
        "C:/Windows/Fonts"
    ]
    
    # Check if it's a common proprietary font and use alternative
    font_name_lower = font_name.lower().replace('-', '').replace(' ', '')
    is_proprietary = font_name_lower in alternatives
    
    if is_proprietary:
        alternative = alternatives[font_name_lower]
        print(f"'{font_name}' is a proprietary font. Using {alternative} as an alternative.")
        
        # Look for the alternative in system fonts
        for font_location in system_font_locations:
            try:
                # Create filesystem object
                font_fs = fs.open_fs(os.path.expanduser(font_location))
                
                # Walk through all directories
                for path, _, files in font_fs.walk.walk():
                    for file_info in files:
                        # Use file_info.name to get the filename
                        if file_info.name.lower() == alternative.lower():
                            # Found the alternative, copy it to our fonts directory
                            src_path = os.path.join(path, file_info.name).lstrip('/')
                            try:
                                with font_fs.open(src_path, 'rb') as src_file:
                                    with open(font_path, 'wb') as dst_file:
                                        shutil.copyfileobj(src_file, dst_file)
                                print(f"Copied {file_info.name} from system fonts to {font_path}")
                                return font_path
                            except Exception as e:
                                print(f"Error copying font: {e}")
                
                font_fs.close()
            except fs.errors.FSError:
                # Skip if directory doesn't exist or can't be accessed
                pass
    
    # Search for the exact font in system
    for font_location in system_font_locations:
        try:
            # Create filesystem object
            font_fs = fs.open_fs(os.path.expanduser(font_location))
            
            # Walk through all directories
            for path, _, files in font_fs.walk.walk():
                for file_info in files:
                    # Use file_info.name to get the filename
                    if file_info.name.lower() == font_name.lower():
                        # Found the font, copy it to our fonts directory
                        src_path = os.path.join(path, file_info.name).lstrip('/')
                        try:
                            with font_fs.open(src_path, 'rb') as src_file:
                                with open(font_path, 'wb') as dst_file:
                                    shutil.copyfileobj(src_file, dst_file)
                            print(f"Copied {file_info.name} from system fonts to {font_path}")
                            return font_path
                        except Exception as e:
                            print(f"Error copying font: {e}")
            
            font_fs.close()
        except fs.errors.FSError:
            # Skip if directory doesn't exist or can't be accessed
            pass
    
    # If not found in system, try to download directly from Google Fonts
    print("Font not found in system, attempting to download...")
    
    try:
        # Extract font family from filename
        font_family = os.path.splitext(font_name)[0].split('-')[0]
        print(f"Attempting to download {font_family} using fontify...")
        
        try:
            # Extract the font family from filename (e.g. "AntonSC.ttf" → "AntonSC")
            font_family = os.path.splitext(font_name)[0].split('-')[0]
            print(f"Attempting to download {font_family} TTF using download_google_font...")

            # Create the expected font filename for download (assuming TTF format)
            font_file = font_family

            # Use the download_google_font function to fetch and install the font
            font_path = download_font(font_file)
            
            if font_path:
                print(f"Successfully downloaded and installed {font_path}")
                return font_path
            else:
                print(f"Font {font_name} was not downloaded successfully.")
        except Exception as e:
            print(f"Error during font download: {e}")
        
        # If gftools fails, try the direct download approach as fallback
        print("Trying direct download as fallback...")
        
        # If it's a proprietary font, download the DejaVu alternative
        if is_proprietary:
            dejavu_font = alternatives[font_name_lower]
            
            if not os.path.exists(os.path.join(fonts_dir, dejavu_font)):
                dejavu_urls = {
                    "DejaVuSans.ttf": "https://dejavu-fonts.github.io/Files/dejavu-sans-ttf-2.37.zip",
                    "DejaVuSerif.ttf": "https://dejavu-fonts.github.io/Files/dejavu-serif-ttf-2.37.zip",
                    "DejaVuSansMono.ttf": "https://dejavu-fonts.github.io/Files/dejavu-sans-mono-ttf-2.37.zip"
                }
                
                if dejavu_font in dejavu_urls:
                    try:
                        url = dejavu_urls[dejavu_font]
                        print(f"Downloading {dejavu_font} from {url}")
                        
                        # Download zip file
                        response = requests.get(url)
                        if response.status_code == 200:
                            # Extract the TTF file
                            zip_file = zipfile.ZipFile(BytesIO(response.content))
                            ttf_files = [f for f in zip_file.namelist() if f.lower().endswith('.ttf')]
                            
                            # Find the specific font
                            for ttf in ttf_files:
                                if dejavu_font.lower() in ttf.lower():
                                    with open(os.path.join(fonts_dir, dejavu_font), 'wb') as f:
                                        f.write(zip_file.read(ttf))
                                    print(f"Downloaded {dejavu_font}")
                                    # Update font_path to point to the downloaded alternative
                                    font_path = os.path.join(fonts_dir, dejavu_font)
                                    return font_path
                    except Exception as e:
                        print(f"Error downloading DejaVu font: {e}")
    except Exception as e:
        print(f"Error in font download process: {e}")
    
    # Fallback to Roboto as a last resort
    print("Using Roboto as final fallback")
    roboto_url = "https://github.com/google/fonts/raw/main/apache/roboto/static/Roboto-Regular.ttf"
    fallback_font = "Roboto-Regular.ttf"
    fallback_path = os.path.join(fonts_dir, fallback_font)
    
    if not os.path.exists(fallback_path):
        try:
            response = requests.get(roboto_url)
            if response.status_code == 200:
                with open(fallback_path, 'wb') as f:
                    f.write(response.content)
                print(f"Downloaded Roboto as fallback font")
        except Exception as e:
            print(f"Error downloading Roboto: {e}")
    
    if os.path.exists(fallback_path):
        return fallback_path
    else:
        # Absolute last resort - use system default font
        print("WARNING: No usable font found. Using system default.")
        return font_path  # This might not exist, but MoviePy will use system default

def load_config(config_file="config.toml"):
    """Load configuration from TOML file with validation"""
    default_config = {
        "number_of_words": 1,
        "font": "Roboto-Black.ttf",
        "font_size": 100,
        "position": "center",
        "text_align": "center",
        "text_colors": ["#00BFFF", "#90EE90", "#FFD700"],
        "stroke_color": "#000000",
        "stroke_width": 6,
        "bg_color": "none",
        "margin": [40, 40],
        "transition": True,
        "highlight": False,
        "highlight_color": "#FFFF00",
        "has_intro_sound": False,
        "intro_sound": "",
        "overlay": False,
        "overlay_video": "",
        "overlay_opacity": 0.5,
    }
    
    try:
        with open(config_file, "rb") as f:
            config = tomllib.load(f)
            
            # Ensure all required keys exist
            for key, value in default_config.items():
                if key not in config:
                    print(f"Warning: Missing '{key}' in config, using default: {value}")
                    config[key] = value
            
            # Validate values
            if config["number_of_words"] < 1:
                print(f"Warning: 'number_of_words' must be at least 1, setting to 1")
                config["number_of_words"] = 1
            
            if config["font_size"] < 10 or config["font_size"] > 500:
                print(f"Warning: 'font_size' must be between 10 and 500, clamping to valid range")
                config["font_size"] = max(10, min(500, config["font_size"]))
                
            # valid_positions = ["top", "center", "bottom"]
            # if config["position"] not in valid_positions:
            #     print(f"Warning: 'position' must be one of {valid_positions}, setting to 'center'")
            #     config["position"] = "center"
            
            valid_alignments = ["left", "center", "right"]
            if config["text_align"] not in valid_alignments:
                print(f"Warning: 'text_align' must be one of {valid_alignments}, setting to 'center'")
                config["text_align"] = "center"
                
            if not isinstance(config["text_colors"], list) or len(config["text_colors"]) == 0:
                print(f"Warning: 'text_colors' must be a non-empty list, using defaults")
                config["text_colors"] = default_config["text_colors"]
            
            if config["stroke_width"] < 0 or config["stroke_width"] > 20:
                print(f"Warning: 'stroke_width' must be between 0 and 20, clamping to valid range")
                config["stroke_width"] = max(0, min(20, config["stroke_width"]))
            
            if config["bg_color"].lower() == "none":
                config["bg_color"] = None
            
            if not isinstance(config["margin"], list) or len(config["margin"]) != 2:
                print(f"Warning: 'margin' must be a list of two integers, using default")
                config["margin"] = default_config["margin"]
                
            if not isinstance(config["highlight"], bool):
                print(f"Warning: 'highlight' must be a boolean, setting to {default_config['highlight']}")
                config["highlight"] = default_config["highlight"]
                
            if not isinstance(config["transition"], bool):
                print(f"Warning: 'transition' must be a boolean, setting to {default_config['transition']}")
                config["transition"] = default_config["transition"]
                
            if config["overlay_opacity"] < 0 or config["overlay_opacity"] > 1:
                print(f"Warning: 'overlay_opacity' must be between 0.0 and 1.0, clamping to valid range")
                config["overlay_opacity"] = max(0, min(1, config["overlay_opacity"]))
                
            return config
    except FileNotFoundError:
        print(f"Config file {config_file} not found. Using default configuration.")
        return default_config
    except Exception as e:
        print(f"Error loading config from {config_file}: {e}")
        print("Using default configuration")
        return default_config

def parse_position(position, video_width, video_height):
    """
    Parse the position configuration to get absolute coordinates
    
    Args:
        position (str or list): Position specification
        video_width (int): Width of the video
        video_height (int): Height of the video
    
    Returns:
        tuple: (x, y) coordinates for positioning
    """
    # Default to center if None or empty
    if position is None or position == "center":
        return ('center', 'center')
    
    # Predefined positions
    predefined_positions = {
        "top": ('center', 0.1),
        "bottom": ('center', 0.9),
        "top-left": (0.1, 0.1),
        "top-right": (0.9, 0.1),
        "bottom-left": (0.1, 0.9),
        "bottom-right": (0.9, 0.9)
    }
    
    # Check if it's a predefined position
    if isinstance(position, str):
        if position in predefined_positions:
            return predefined_positions[position]
    
    # Handle list or tuple input (either pixels or percentages)
    if isinstance(position, (list, tuple)) and len(position) == 2:
        x, y = position
        
        # Convert percentage to absolute coordinates if needed
        def convert_to_pixel(val, total_size):
            if isinstance(val, str):
                # Remove % sign and convert to float
                if val.endswith('%'):
                    val = float(val.rstrip('%')) / 100.0
                    return int(val * total_size)
                # Handle other string formats if needed
                raise ValueError(f"Invalid position value: {val}")
            elif isinstance(val, (int, float)):
                # If less than 1, treat as percentage
                if 0 <= val <= 1:
                    return int(val * total_size)
                # If greater than 1, treat as pixel value
                return int(val)
            else:
                raise ValueError(f"Invalid position type: {type(val)}")
        
        try:
            x_pixel = convert_to_pixel(x, video_width)
            y_pixel = convert_to_pixel(y, video_height)
            return ('center', y_pixel)
        except Exception as e:
            print(f"Error parsing position: {e}")
            return ('center', 'center')
    
    # Fallback to center
    return ('center', 'center')

def add_captions_to_video(input_video_path, output_path=None, config_path="config.toml"):
    """
    Add animated captions to a video file
    
    Args:
        input_video_path (str): Path to input video file
        output_path (str): Path for output video (if None, will use input path + '_captioned')
        config_path (str): Path to configuration file
    """
    # Load configuration
    config = load_config(config_path)
    
    temp_audio = "temp_audio.wav"
    
    if output_path is None:
        # Generate output path based on input path
        base, ext = os.path.splitext(input_video_path)
        output_path = f"{base}_captioned{ext}"

    # Load the video
    print(f"Loading video: {input_video_path}")
    video = VideoFileClip(input_video_path)
    
    # Handle overlay video if configured
    if config["overlay"] and config["overlay_video"] and os.path.exists(config["overlay_video"]):
        print(f"Adding overlay video: {config['overlay_video']}")
        overlay_clip = VideoFileClip(config["overlay_video"])
        
        # Resize overlay to match the main video's dimensions
        overlay_clip = overlay_clip.resize(height=video.h)
        
        # Set opacity
        overlay_clip = overlay_clip.with_opacity(config["overlay_opacity"])
        
        # Composite with main video
        video = CompositeVideoClip([video, overlay_clip.with_position('center')])
    
    # Handle intro sound if configured
    if config["has_intro_sound"] and config["intro_sound"] and os.path.exists(config["intro_sound"]):
        print(f"Adding intro sound: {config['intro_sound']}")
        intro_audio = AudioFileClip(config["intro_sound"])
        original_audio = video.audio
        new_audio = CompositeAudioClip([original_audio, intro_audio.with_start(0)])
        video = video.with_audio(new_audio)
    
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

    # Define colors to cycle through
    colors = cycle(config["text_colors"])
    
    # Convert position string to coordinates
    position_map = {
        "top": ('center', 0.1),
        "center": ('center', 'center'),
        "bottom": ('center', 0.9)
    }
    position = parse_position(config["position"], video.w, video.h)
    
    # Make sure font path exists
    font_path = ensure_font_exists(config["font"])
    if not os.path.exists(font_path):
        print(f"Warning: Font {font_path} could not be found or downloaded")
        # Try to use a system font as absolute last resort
        system_fonts = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux
            "/Library/Fonts/Arial.ttf",  # macOS
            "C:\\Windows\\Fonts\\arial.ttf"  # Windows
        ]
        for system_font in system_fonts:
            if os.path.exists(system_font):
                font_path = system_font
                print(f"Using system font: {font_path}")
                break

    # Group words based on number_of_words configuration
    subtitle_clips = []
    
    # Process each segment in the transcript
    for segment in result["segments"]:
        word_buffer = []
        word_start_times = []
        word_end_times = []
        
        # Process each word in the segment
        for word_info in segment.get("words", []):
            word = word_info["word"].strip()
            start = word_info["start"]
            end = word_info["end"]
            
            if not word or word.isspace():
                continue
            
            # Add word to the buffer
            word_buffer.append(word)
            word_start_times.append(start)
            word_end_times.append(end)
            
            # If we've reached the desired number of words, create a text clip
            if len(word_buffer) >= config["number_of_words"]:
                # Calculate start and end times for the group
                group_start = word_start_times[0]
                group_end = word_end_times[-1]
                duration = group_end - group_start
                
                # For highlighting, we need to use a custom approach with PIL
                if config["highlight"] and config["number_of_words"] > 1:
                    
                    for i in range(len(word_buffer)):
                        word_start = word_start_times[i]
                        word_end = word_end_times[i]
                        word_duration = word_end - word_start
                        
                        # Create a clip with the current word highlighted
                        txt_clip = create_highlighted_word_clip(
                            word_buffer, 
                            i, 
                            font_path, 
                            video.w, 
                            config
                        )
                        
                        # Only apply zoom animation for the first word if transitions are enabled
                        if i == 0:
                            txt_clip = txt_clip.transform(make_zoom_transform(word_duration, config["transition"]))
                        
                        # Set timing and position
                        txt_clip = (txt_clip
                                   .with_start(word_start)
                                   .with_duration(word_duration)
                                   .with_position(position))
                        
                        subtitle_clips.append(txt_clip)
                else:
                    # Standard case: single clip for all words
                    color = next(colors)
                    
                    # Create a TextClip with all the configured properties
                    txt_clip = TextClip(
                        font=font_path,
                        text=" ".join(word_buffer),
                        font_size=config["font_size"],
                        size=(video.w, None),
                        color=color,
                        stroke_color=config["stroke_color"],
                        stroke_width=config["stroke_width"],
                        method='caption',
                        bg_color=config["bg_color"],
                        margin=tuple(config["margin"]),
                        text_align=config["text_align"]
                    )
                    
                    # Add zoom animation if transitions are enabled
                    txt_clip = txt_clip.transform(make_zoom_transform(duration, config["transition"]))
                    
                    # Set timing and position
                    txt_clip = (txt_clip
                               .with_start(group_start)
                               .with_duration(duration)
                               .with_position(position))
                    
                    subtitle_clips.append(txt_clip)
                
                # Reset buffers for next group
                word_buffer = []
                word_start_times = []
                word_end_times = []
        
        # Handle any remaining words in the buffer
        if word_buffer:
            group_start = word_start_times[0]
            group_end = word_end_times[-1]
            duration = group_end - group_start
            
            # For highlighting with multiple words remaining
            if config["highlight"] and len(word_buffer) > 1:
                
                for i in range(len(word_buffer)):
                    word_start = word_start_times[i]
                    word_end = word_end_times[i]
                    word_duration = word_end - word_start
                    
                    # Create a clip with the current word highlighted
                    txt_clip = create_highlighted_word_clip(
                        word_buffer, 
                        i, 
                        font_path, 
                        video.w, 
                        config
                    )
                    
                    # Only apply zoom animation for the first word if transitions are enabled
                    if i == 0:
                        txt_clip = txt_clip.transform(make_zoom_transform(word_duration, config["transition"]))
                    
                    # Set timing and position
                    txt_clip = (txt_clip
                               .with_start(word_start)
                               .with_duration(word_duration)
                               .with_position(position))
                    
                    subtitle_clips.append(txt_clip)
            else:
                # Standard case - single text clip for all words
                color = next(colors)
                
                # Create a TextClip with all the configured properties
                txt_clip = TextClip(
                    font=font_path,
                    text=" ".join(word_buffer),
                    font_size=config["font_size"],
                    size=(video.w, None),
                    color=color,
                    stroke_color=config["stroke_color"],
                    stroke_width=config["stroke_width"],
                    method='caption',
                    bg_color=config["bg_color"],
                    margin=tuple(config["margin"]),
                    text_align=config["text_align"]
                )
                
                # Add zoom animation if transitions are enabled
                txt_clip = txt_clip.transform(make_zoom_transform(duration, config["transition"]))
                
                # Set timing and position
                txt_clip = (txt_clip
                           .with_start(group_start)
                           .with_duration(duration)
                           .with_position(position))
                
                subtitle_clips.append(txt_clip)

    # Create final video with captions
    final_video = CompositeVideoClip([video] + subtitle_clips)

    print(f"Writing output video with captions to: {output_path}")
    final_video.write_videofile(output_path, codec="libx264", audio_codec="aac")

    # Clean up
    video.close()
    final_video.close()
    print("Captioning complete!")

def main():
    parser = argparse.ArgumentParser(description='Add animated captions to a video')
    parser.add_argument('video_file', help='Input video file')
    parser.add_argument('--output_file', default=None, help='Output video file (default: input_file_captioned.ext)')
    parser.add_argument('--config', default='config.toml', help='Configuration file (default: config.toml)')
    
    args = parser.parse_args()
    
    add_captions_to_video(args.video_file, args.output_file, args.config)

if __name__ == '__main__':
    main()