"""Download all files from Supabase Storage buckets."""
import json
import os
import sys
from urllib import request as urlrequest, error as urlerror
from urllib.parse import quote

sys.stdout.reconfigure(encoding='utf-8')

SUPABASE_URL = "https://ryuvcdthjnxyetdyjbph.supabase.co"
SERVICE_ROLE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJ5dXZjZHRoam54eWV0ZHlqYnBoIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NTI5MTI2MywiZXhwIjoyMDkwODY3MjYzfQ.n6alwTEqx9d3WxswCFfbYBWPmigLhO9c7QKXiM5ofMw"

def list_storage_objects(bucket_name):
    """List all objects in a Supabase Storage bucket."""
    url = f"{SUPABASE_URL}/storage/v1/object/list/{bucket_name}"
    # List with empty search to get all files
    payload = json.dumps({"prefix": ""}).encode()
    req = urlrequest.Request(
        url=url,
        data=payload,
        headers={
            "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
            "apikey": SERVICE_ROLE_KEY,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlrequest.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"  ERROR listing {bucket_name}: {e}", flush=True)
        return []

def download_file(bucket_name, file_path, local_dir):
    """Download a single file from Supabase Storage."""
    encoded_path = quote(file_path, safe='')
    url = f"{SUPABASE_URL}/storage/v1/object/{bucket_name}/{encoded_path}"
    req = urlrequest.Request(
        url=url,
        headers={
            "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
            "apikey": SERVICE_ROLE_KEY,
        },
        method="GET",
    )
    try:
        with urlrequest.urlopen(req, timeout=60) as resp:
            content = resp.read()
            local_path = os.path.join(local_dir, os.path.basename(file_path))
            # Handle nested paths
            if '/' in file_path:
                subdir = os.path.dirname(file_path)
                full_dir = os.path.join(local_dir, subdir)
                os.makedirs(full_dir, exist_ok=True)
                local_path = os.path.join(full_dir, os.path.basename(file_path))

            with open(local_path, 'wb') as f:
                f.write(content)
            return True
    except urlerror.HTTPError as e:
        if e.code == 404:
            print(f"  404: {file_path}", flush=True)
        else:
            print(f"  HTTP {e.code}: {file_path}", flush=True)
    except Exception as e:
        print(f"  ERROR downloading {file_path}: {e}", flush=True)
    return False

# Download from question-images bucket
print("=== Downloading question images ===", flush=True)
images_dir = '../backup/supabase_storage_images'
os.makedirs(images_dir, exist_ok=True)
image_files = list_storage_objects("crack-cms-question-images")
print(f"Found {len(image_files)} image objects", flush=True)
downloaded = 0
for obj in image_files:
    name = obj.get('name', '')
    if not name:
        continue
    if download_file("crack-cms-question-images", name, images_dir):
        downloaded += 1
    if downloaded % 50 == 0 and downloaded > 0:
        print(f"  ... {downloaded}/{len(image_files)} downloaded", flush=True)
print(f"Downloaded {downloaded} images", flush=True)

# Download from educational-videos bucket
print("\n=== Downloading educational videos ===", flush=True)
videos_dir = '../backup/supabase_storage_videos'
os.makedirs(videos_dir, exist_ok=True)
video_files = list_storage_objects("educational_videos")
print(f"Found {len(video_files)} video objects", flush=True)
downloaded = 0
for obj in video_files:
    name = obj.get('name', '')
    if not name:
        continue
    if download_file("educational_videos", name, videos_dir):
        downloaded += 1
    if downloaded % 10 == 0 and downloaded > 0:
        print(f"  ... {downloaded}/{len(video_files)} downloaded", flush=True)
print(f"Downloaded {downloaded} videos", flush=True)

print("\n=== Storage backup complete ===", flush=True)
