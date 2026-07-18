import os
import django
import json
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
django.setup()

from django.core import serializers
from django.db import transaction

def load_data(file_path):
    print(f"Reading file {file_path}...")
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print("Sorting data to resolve dependencies...")
    # Order of models to load
    order = {
        'accounts.customuser': 1,
        'questions.subject': 2,
        'questions.topic': 3,
        'questions.question': 4,
    }
    
    data.sort(key=lambda x: order.get(x['model'], 100))

    data_str = json.dumps(data)

    print("Deserializing data...")
    # collect forward references
    deserializer = serializers.deserialize("json", data_str, ignorenonexistent=True, handle_forward_references=True)
    
    objects = []
    for obj in deserializer:
        objects.append(obj)
        
    total = len(objects)
    print(f"Total objects to load: {total}")

    batch_size = 100
    for i in range(0, total, batch_size):
        batch = objects[i:i+batch_size]
        try:
            with transaction.atomic():
                for obj in batch:
                    # obj is a DeserializedObject. We need to save it.
                    obj.save()
            print(f"Saved {min(i+batch_size, total)} / {total} objects")
        except Exception as e:
            print(f"Error in batch {i} to {i+batch_size}: {e}")
            for obj in batch:
                try:
                    obj.save()
                except Exception as e2:
                    print(f"Failed to save {obj.object}: {e2}")

if __name__ == '__main__':
    load_data('../data_dump.json')
