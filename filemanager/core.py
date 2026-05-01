from pathlib import Path
from datetime import datetime

BASE_DIR = Path.cwd()
DT_TEMPLATE = '%Y-%m-%d %H:%M:%S'

def is_path_exists(path: Path):
    return path.exists()

def is_path_dir(path: Path):
    return path.is_dir()

def list_directory(path: Path):
    if not is_path_exists(path):
        return { 'success': False, 'error': "File/Dir doesn't exist."}
    
    if not is_path_dir(path):
        return { 'success': False, 'error': "It's not a dir."} 
    
    dict_paths = {'success': True, 'data': []}

    for child in path.iterdir():        
        stats = child.stat()
        datetime_child = datetime.fromtimestamp(stats.st_mtime)
        datetime_child = datetime_child.strftime(DT_TEMPLATE)
        
        obj_child = {
            'name': child.name, 
            'path': str(child), 
            'type': 'directory' if is_path_dir(child) else 'file', 
            'size': stats.st_size, 
            'modified_at': datetime_child, 
            'extension': child.suffix
        }
        
        dict_paths['data'].append(obj_child)
    
    return dict_paths
        
if __name__ == '__main__':
    print(list_directory(BASE_DIR))

