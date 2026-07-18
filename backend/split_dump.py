import json
import os

def split_dump():
    with open('../data_dump.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    order = {
        'accounts.customuser': 1,
        'questions.subject': 2,
        'questions.topic': 3,
        'questions.question': 4,
    }
    
    data.sort(key=lambda x: order.get(x['model'], 100))
    
    chunk_size = 1000
    for i in range(0, len(data), chunk_size):
        chunk = data[i:i+chunk_size]
        filename = f'../data_dump_chunk_{i//chunk_size}.json'
        with open(filename, 'w', encoding='utf-8') as f_out:
            json.dump(chunk, f_out, indent=2)
        print(f"Created {filename} with {len(chunk)} objects.")

if __name__ == '__main__':
    split_dump()
