# filemanager

> ⚠️ This project is currently under development and is not ready for use.

A Python library for safe file system operations within a root directory.

## Features

- List directory contents with metadata
- Search files and directories with multiple filters
- Safe path resolution (prevents path traversal attacks)
- Configurable date format and sortable fields
- Sortable results by any field, ascending or descending
- Recursive directory traversal with symlink protection
- Suport for hidden files/folders.

## Installation

**From source (development):**
```bash
pip install -e .
```

## Usage

```python
from pathlib import Path
from filemanager import FileManager

fm = FileManager('/home/user/documents')

# List directory
fm.list_directory(Path('.'))

# List with ordering
fm.list_directory(Path('.'), order_by='name')
fm.list_directory(Path('.'), order_by='-size')

# List recursively
fm.list_directory(Path('.'), recursive=True)

# Search by name
list(fm.search(name='report'))

# Search by extension
list(fm.search(extension='pdf'))

# Search by size range
list(fm.search(min_size=1000, max_size=5000))

# Search with multiple filters
list(fm.search(name='report', extension='pdf', min_size=1000))

# Search recursively
list(fm.search(name='report', recursive=True))
```

## Configuration

```python
fm = FileManager(
    root_dir='/home/user/documents',
    dt_template='%d/%m/%Y %H:%M:%S',   # custom date format
    valid_order_fields={'name', 'size'}  # custom sortable fields
)
```

## Running Tests

```bash
pytest
```

## Roadmap

### In Development
- [x] `list_directory` — List directory contents with metadata
- [x] `search` — Search files and directories with multiple filters
- [ ] `info` — Get detailed metadata of a file or directory
- [x] `mkdir` — Create a new directory
- [ ] `delete` — Delete a file or directory
- [x] `move` — Move or rename a file or directory
- [x] `touch` — Create a new file.
- [ ] `copy` — Copy a file or directory
- [ ] `upload` — Save a file from bytes
- [ ] `download` — Read and return file bytes

### Planned
- [ ] CLI interface via Click or Argparse

## License

MIT
