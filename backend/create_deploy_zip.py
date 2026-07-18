import os
import zipfile

def create_zip():
    source_dir = r"c:\Users\DIVYANSHU\Desktop\crack_cms\backend"
    zip_path = r"c:\Users\DIVYANSHU\Desktop\backend_deploy.zip"
    
    # Folders to completely skip
    exclude_dirs = {'venv', '.venv', '__pycache__', 'Medura_Train', 'chroma_db'}
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_dir):
            # Modify dirs in-place to skip excluded directories
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                # Skip duplicate pdfs if they somehow made it here
                if file.startswith('Copy of') and file.endswith('.pdf'):
                    continue
                if file.endswith('.exe'):
                    continue
                    
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, source_dir)
                zipf.write(file_path, arcname)

if __name__ == "__main__":
    create_zip()
    print("Deployment zip created at c:\\Users\\DIVYANSHU\\Desktop\\backend_deploy.zip")
