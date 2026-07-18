import os
import django
import json
import sys
import time

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
django.setup()

from django.core import serializers
from django.db import transaction

def load_data(file_path):
    print(f"Reading file {file_path}...")
    with open(file_path, 'r', encoding='utf-8') as f:
        data = f.read()

    print("Deserializing data...")
    deserializer = serializers.deserialize("json", data, ignorenonexistent=True, handle_forward_references=True)
    
    count = 0
    for obj in deserializer:
        count += 1
        print(f"Loading {count}: {obj.object.__class__.__name__} pk={obj.object.pk}...")
        try:
            start = time.time()
            obj.save()
            print(f"Saved {obj.object.__class__.__name__} pk={obj.object.pk} in {time.time()-start:.2f}s")
        except Exception as e:
            print(f"Failed to save {obj.object.__class__.__name__} pk={obj.object.pk}: {e}")

if __name__ == '__main__':
    load_data('../data_dump_chunk_0.json')
