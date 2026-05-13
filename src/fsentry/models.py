from dataclasses import dataclass
from pathlib import Path
import os

@dataclass(slots=True)
class FileEntry:
    display_path: Path
    resolved_path: Path
    stat_result: os.stat_result
    is_link: bool
    is_dir: bool
    
    @property
    def name(self) -> str:
        return self.display_path.name
    
    @property
    def extension(self) -> str:
        return self.display_path.suffix.lstrip(".")
    
    @property
    def type(self) -> str:
        return "directory" if self.is_dir else "file"
    
    @property
    def size(self) -> int:
        return self.stat_result.st_size
