import os
import requests

def main():
    fonts_dir = r"C:\Users\Lenovo\.gemini\antigravity\scratch\youth_club_library\static\fonts"
    os.makedirs(fonts_dir, exist_ok=True)
    
    font_urls = {
        "NotoSansBengali-Regular.ttf": "https://raw.githubusercontent.com/notofonts/noto-fonts/main/hinted/ttf/NotoSansBengali/NotoSansBengali-Regular.ttf",
        "NotoSansBengali-Bold.ttf": "https://raw.githubusercontent.com/notofonts/noto-fonts/main/hinted/ttf/NotoSansBengali/NotoSansBengali-Bold.ttf"
    }
    
    for filename, url in font_urls.items():
        dest_path = os.path.join(fonts_dir, filename)
        if os.path.exists(dest_path):
            print(f"Font already exists: {filename}")
            continue
            
        print(f"Downloading {filename} from {url}...")
        try:
            res = requests.get(url, timeout=30)
            res.raise_for_status()
            with open(dest_path, "wb") as f:
                f.write(res.content)
            print(f"Successfully saved {filename} to {dest_path}")
        except Exception as e:
            print(f"Failed to download {filename}: {e}")

if __name__ == "__main__":
    main()
