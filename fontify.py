#!/usr/bin/env python3
import argparse
import os
import re
import sys
import requests
from urllib.parse import quote_plus, urlparse

def download_font(font_name):
    # Prepare the Google Fonts API URL.
    # Replace spaces with '+' using quote_plus.
    encoded_name = quote_plus(font_name)
    api_url = f"https://fonts.googleapis.com/css2?family={encoded_name}"
    
    # Google Fonts API requires a proper User-Agent header.
    headers = {"User-Agent": "Mozilla/5.0"}
    
    print(f"Querying Google Fonts API for '{font_name}'...")
    response = requests.get(api_url, headers=headers)
    
    if response.status_code != 200:
        print(f"Error: Font '{font_name}' not found (HTTP {response.status_code}).")
        sys.exit(1)
    
    css_text = response.text
    
    # Look for a URL in the CSS (this example takes the first occurrence).
    # This regex finds patterns like: url(https://fonts.gstatic.com/....)
    match = re.search(r"url\((https?://[^)]+)\)", css_text)
    if not match:
        print("Could not find a downloadable font URL in the returned CSS.")
        sys.exit(1)
    
    font_url = match.group(1)
    print(f"Found font file URL: {font_url}")
    
    # Download the font file.
    font_response = requests.get(font_url, headers=headers)
    if font_response.status_code != 200:
        print(f"Error downloading font file (HTTP {font_response.status_code}).")
        return
    
    # Determine the file extension from the URL.
    parsed_url = urlparse(font_url)
    filename = os.path.basename(parsed_url.path)
    ext = os.path.splitext(filename)[1]
    if not ext:
        ext = ".ttf"  # fallback
    
    # Sanitize the font name for the filename.
    safe_font_name = "".join(c if c.isalnum() else "_" for c in font_name)
    out_dir = "./fonts"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{safe_font_name}{ext}")
    
    with open(out_path, "wb") as f:
        f.write(font_response.content)
    
    print(f"Font '{font_name}' downloaded and saved to '{out_path}'.")
    return out_path

def main():
    parser = argparse.ArgumentParser(
        description="Download a font from Google Fonts by its name."
    )
    parser.add_argument(
        "font_name",
        type=str,
        help="The name of the font to download (e.g., 'Open Sans')."
    )
    args = parser.parse_args()
    download_font(args.font_name)

if __name__ == "__main__":
    main()
