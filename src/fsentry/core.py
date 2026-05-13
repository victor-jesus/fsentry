from pathlib import Path
from datetime import datetime
from collections.abc import Generator
import stat
import shutil

from fsentry.models import FileEntry
from fsentry.serializers import serialize_entry
from fsentry.security import safe_resolve, is_key_valid, ensure_dir, ensure_exists

class Fsentry():
    """
    A file manager that provides safe file system operations within a root directory.

    Args:
        root_dir: The root directory to operate within. Accepts str or Path.
        dt_template: The str for date format in outputs.
        valid_order_fields: The set that determines the default keys.

    Raises:
        ValueError: If the root directory does not exist.
        NotADirectoryError: If the root path is not a directory.

    Example:
        >>> fm = Fsentry('/home/user/documents', '%d-%m-%Y %H:%M:%S', {'name', 'path', 'type', 'size', 'modified_at', 'extension'})
        >>> fm.list_directory(Path('.'))
    """

    def __init__(
        self, 
        root_dir: str | Path, 
        dt_template: str = '%Y-%m-%d %H:%M:%S', 
        valid_order_fields: set | None = None
    ):
        
        self._root_dir = Path(root_dir).resolve()
        self.DT_TEMPLATE = dt_template
        self.VALID_ORDER_FIELDS = (
            valid_order_fields if valid_order_fields is not None 
            else {'name', 'path', 'type', 'size', 'modified_at', 'extension', 'is_symbolic_link'}
        )
        
        if not self._root_dir.exists():
            raise ValueError("Root directory doesn't exists.")
        if not self._root_dir.is_dir():
            raise NotADirectoryError("Root must be a directory.")

    def _order_by_key_normalize(self, key: str) -> tuple:
        """
        Parses an order_by key into field name and sort direction.

        Returns:
            A tuple of (field: str, reverse: bool).

        Example:
            >>> self._order_by_key_normalize('-name')
            ('name', True)
            >>> self._order_by_key_normalize('name')
            ('name', False)
        """
        reverse = key.startswith('-')
        field = key[1:] if reverse else key
        return field, reverse
        
    def _get_formatted_date(self, sm_mtime):
        datetime_path = datetime.fromtimestamp(sm_mtime)
        return datetime_path.strftime(self.DT_TEMPLATE)
        
    def _build_entry(
        self,
        path: Path,
        hidden_files: bool = False,
        allow_symbolic_links: bool = False
    ) -> FileEntry | None:
        """
            Validate and returns an object of type FileEntry.
        """
        if not hidden_files and path.name.startswith("."):
            return
                    
        # Symlink verification         
        try:
            link_stat = path.lstat()
        except (PermissionError, FileNotFoundError):
            return None
        
        is_link = stat.S_ISLNK(link_stat.st_mode)
        if is_link and not allow_symbolic_links:
            return
        
        try:
            resolved = safe_resolve(path, self._root_dir)
        except PermissionError:
            return None
        
        try:
            st = path.stat() if is_link else link_stat
        except (PermissionError, FileNotFoundError):
            return None
        
        is_dir = stat.S_ISDIR(st.st_mode)
                        
        return FileEntry(
            display_path=path, 
            resolved_path=resolved,
            stat_result=st,  
            is_link=is_link,
            is_dir=is_dir
        )
    
    def _iter_directory(
        self, 
        path: Path, 
        allow_symbolic_links: bool = False,
        hidden_files: bool = False,
        recursive: bool = False) -> Generator[FileEntry, None, None]:
        """
        Iterate through a directory using multiple permissions.
        This method is lazy (generator-based), yielding results incrementally.

        Args:
            path: Directory to search. Defaults to root ('.').
            allow_symbolic_links: If False, symbolic links are excluded.
            hidden_files: If False, hidden files are excluded.
            recursive: If True, search includes subdirectories.

        Yields:
            FileEntry: from models FileEntry.

        Raises:
            PermissionError: If the path is outside the root directory (Symbolic Link included).
            FileNotFoundError: If the path does not exist.
            NotADirectoryError: If the path is not a directory.
            ValueError: If min_size > max_size.
    
        Example:
            >>> list(fm.search(name="report", recursive=True))
            >>> list(fm.search(extension="pdf", min_size=1000))
        """
        resolved_path = safe_resolve(path, root_dir=self._root_dir)
        ensure_exists(resolved_path)
        ensure_dir(resolved_path)
        
        stack = [resolved_path]
        visited = set()
        
        while stack:
            current_path = stack.pop()
            
            if current_path in visited:
                continue
            visited.add(current_path)
            
            try:
                children = current_path.iterdir()
            except (PermissionError, ValueError):
                continue
            
            for child in children:       
                entry = self._build_entry(
                    child,
                    hidden_files=hidden_files,
                    allow_symbolic_links=allow_symbolic_links
                )           
                
                if entry is None: continue
                                     
                yield entry
                
                if recursive and entry.is_dir:
                    if entry.display_path not in visited:
                        stack.append(entry.display_path)
              
    def search(
        self, 
        name: str | None = None,
        extension: str | None = None,
        min_size: int | None = None,
        max_size: int | None = None,
        contains: str | None = None,
        allow_symbolic_links: bool = False,
        hidden_files: bool = False, 
        recursive: bool = False,
        path: Path | None = None) -> Generator[dict, None, None]:
        """
        Searches for files and directories using multiple filters.
        This method is lazy (generator-based), yielding results incrementally.

        Args:
            name: Case-insensitive substring match against the name.
            extension: Exact match for file extension (case-insensitive).
            min_size: Minimum size in bytes (inclusive).
            max_size: Maximum size in bytes (inclusive).
            contains: Case-insensitive substring match across all fields.
            allow_symbolic_links: If False, symbolic links are excluded.
            hidden_files: If False, hidden files are excluded.
            recursive: If True, search includes subdirectories.
            path: Directory to search. Defaults to root ('.').

        Yields:
            FieldEntry
            
        Raises:
            PermissionError: If the path is outside the root directory.
            FileNotFoundError: If the path does not exist.
            NotADirectoryError: If the path is not a directory.
            ValueError: If min_size > max_size.
            
        Notes:
            - Delegates traversal to `iter_directory`.
            - Filtering is performed in-memory per item (no indexing).

        Example:
            >>> list(fm.search(name="report", recursive=True))
            >>> list(fm.search(extension="pdf", min_size=1000))
        """
        if min_size is not None and max_size is not None:
            if min_size > max_size:
                raise ValueError('Minimum size must be lower than maximum size.') 
            
        path = path or Path('.')
        
        predicates = []
        
        if name:
            name_lower = name.lower()
            predicates.append(lambda entry: name_lower in entry.name.lower())

        if extension:
            ext_lower = extension.lower().lstrip(".")
            predicates.append(lambda entry: entry.extension.lower() == ext_lower)

        if min_size is not None:
            predicates.append(lambda entry: entry.size >= min_size)

        if max_size is not None:
            predicates.append(lambda entry: entry.size <= max_size)
            
        if contains:
            contains_lower = contains.lower()
            predicates.append(
                lambda entry: (
                    contains_lower in entry.name.lower()
                    or contains_lower in entry.extension.lower()
                    or contains_lower in str(entry.resolved_path).lower()
                    or contains_lower in entry.type.lower()
                )
            )
            
        for entry in self._iter_directory(path, hidden_files=hidden_files, allow_symbolic_links=allow_symbolic_links, recursive=recursive):
            if all(pred(entry) for pred in predicates):
                data = serialize_entry(
                    entry, 
                    root_dir=self._root_dir,
                    dt_template=self.DT_TEMPLATE
                )
                yield data

    def list_directory(
        self, 
        path: Path, 
        allow_symbolic_links: bool = False,
        hidden_files: bool = False,
        recursive: bool = False, 
        order_by: str | None = None) -> dict:
        """
        Lists directory contents with optional recursion and sorting.
        This method materializes all results into memory.

        Args:
            path: Directory to list. Can be relative to root or absolute.
            allow_symbolic_links: If False, symbolic links are excluded.
            hidden_files: If False, excludes hidden files.
            recursive: If True, includes all subdirectories.
            order_by: Field to sort by. Prefix with '-' for descending.
                Valid fields: name, path, type, size, modified_at, extension.

        Raises:
            PermissionError: If the path is outside the root directory.
            FileNotFoundError: If the path does not exist.
            NotADirectoryError: If the path is not a directory.
            ValueError: If order_by field is invalid.

        Notes:
            - Uses `iter_directory` internally.
            - Sorting is applied after full materialization.

        Example:
            >>> fm.list_directory(Path('.'))
            >>> fm.list_directory(Path('.'), recursive=True, order_by='-size')
        """
        entries = list(self._iter_directory(
            path, 
            hidden_files=hidden_files, 
            recursive=recursive, 
            allow_symbolic_links=allow_symbolic_links
            )
        )

        if order_by:
            field, reverse = self._order_by_key_normalize(order_by)
            is_key_valid(field, self.VALID_ORDER_FIELDS)
            entries = sorted(
                entries,
                key=lambda item: (
                    (getattr(item, field) is None), 
                    (getattr(item, field) or 0) if field == 'size' 
                    else (getattr(item, field) or '')
                ),
                reverse=reverse
            )
        
        data = [
            serialize_entry(
                entry=entry,
                root_dir=self._root_dir,
                dt_template=self.DT_TEMPLATE
            )
            for entry in entries
        ]

        return {
            'total': len(data),
            'data': data
        }
        
    def touch(self, path: Path):
        resolved_path = safe_resolve(path, self._root_dir)
        try:
            resolved_path.touch(exist_ok=False)
        except FileExistsError:
            raise FileExistsError(f'Error: file named {resolved_path.name} already exists.')
        
        entry = self._build_entry(resolved_path, hidden_files=True, allow_symbolic_links=True)
        if entry is None:
            raise RuntimeError(f'Failed to build entry after move: {resolved_path}')  

        return serialize_entry(entry, self._root_dir, dt_template=self.DT_TEMPLATE)
        
    def mkdir(
        self, 
        path: Path, 
        parents: bool = True, 
        exist_ok: bool = True
    ):
        """
                parents: bool -> When creating a file/folder, 
                creates the parents if not exists
                exist_ok: bool -> 
        """
        
        resolved_path = safe_resolve(path, self._root_dir)
        try:
            resolved_path.mkdir(parents=parents, exist_ok=exist_ok)
        except FileExistsError:
            raise FileExistsError(f'Error: folder named {resolved_path.name} already exists.')
        
        entry = self._build_entry(resolved_path, hidden_files=True, allow_symbolic_links=True)
        if entry is None:
            raise RuntimeError(f'Failed to build entry after move: {resolved_path}')  
        
        return serialize_entry(entry, self._root_dir, dt_template=self.DT_TEMPLATE)

        
    def move(
        self, 
        path_source: list[Path], 
        path_destination: Path, 
        parents: bool = True, 
        exist_ok = True
    ):
        resolved_dst = safe_resolve(path_destination, self._root_dir)
        resolved_dst.mkdir(parents=parents, exist_ok=exist_ok)
        
        results = []
        for path in path_source:
            resolved_src = safe_resolve(path, self._root_dir)
            ensure_exists(resolved_src)
            
            final_dst = resolved_dst / resolved_src.name
            
            resolved_src.rename(final_dst)
            
            entry = self._build_entry(final_dst, hidden_files=True, allow_symbolic_links=True)
            if entry is None:
                raise RuntimeError(f'Failed to build entry after move: {final_dst}')  
            
            results.append(serialize_entry(entry, self._root_dir, self.DT_TEMPLATE))          
        
        return results
            
    def copy(
        self, 
        src: Path, 
        dst: Path, 
        parents: bool = True, 
        exist_ok : bool = True
    ) -> dict:
        """
            This function copies the object in src path to dst Path.
            
            If the folder doesn't exists, it will create it.
        """
        src = safe_resolve(src, self._root_dir)
        dst = safe_resolve(dst, self._root_dir)
        ensure_exists(src)
        
        self.mkdir(dst, parents=parents, exist_ok=exist_ok)
        
        if src.is_dir(): 
            shutil.copytree(src, (dst / src.name)) 
        else: 
            shutil.copy2(src, dst)
            
        entry = self._build_entry(dst, hidden_files=True, allow_symbolic_links=True)
        if entry is None: 
            raise RuntimeError(f'Not possible to copy object from {src} to {dst}')
            
        return serialize_entry(entry, self._root_dir, dt_template=self.DT_TEMPLATE)

if __name__ == '__main__':
    fm = Fsentry(Path.cwd())
