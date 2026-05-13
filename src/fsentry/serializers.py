from fsentry.models import FileEntry
from datetime import datetime
from pathlib import Path

def serialize_entry(
    entry: FileEntry,
    root_dir: Path,
    dt_template: str
) -> dict:
    return {
        'name': entry.name,
        'path': str(entry.resolved_path.relative_to(root_dir)),
        'type': entry.type,
        'size': entry.size,
        'modified_at': datetime.fromtimestamp(
            entry.stat_result.st_mtime
        ).strftime(dt_template),
        'extension': entry.extension,
        'is_symbolic_link': entry.is_link
    }