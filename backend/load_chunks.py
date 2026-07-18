import os
import subprocess
import sys

def load_chunks():
    for i in range(7):
        chunk_file = f'../data_dump_chunk_{i}.json'
        print(f"Loading {chunk_file}...")
        result = subprocess.run(
            [sys.executable, 'manage.py', 'loaddata', '-v', '2', chunk_file],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"Error loading {chunk_file}:\n{result.stderr}\n{result.stdout}")
        else:
            print(f"Success loading {chunk_file}:\n{result.stdout}")

if __name__ == '__main__':
    load_chunks()
