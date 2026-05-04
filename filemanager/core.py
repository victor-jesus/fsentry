from pathlib import Path
from datetime import datetime
from collections.abc import Generator

class FileManager():
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
        >>> fm = FileManager('/home/user/documents', '%d-%m-%Y %H:%M:%S', {'name', 'path', 'type', 'size', 'modified_at', 'extension'})
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
            else {'name', 'path', 'type', 'size', 'modified_at', 'extension'}
        )
        
        if not self._root_dir.exists():
            raise ValueError("Root directory doesn't exists.")
        if not self._root_dir.is_dir():
            raise NotADirectoryError("Root must be a directory.")

    def _normalize_path(self, path: Path) -> Path:
        """
        Normalizes a path to be absolute, relative to the root directory.

        If the path is relative, it is joined with the root directory.
        If the path is absolute, it is returned as-is before safe resolution.

        Args:
            path: The path to normalize.

        Returns:
            An absolute Path object.
        """
        if not path.is_absolute():
            path = self._root_dir / path
        return path

    def _is_key_valid(self, key: str) -> None:
        """
        Validates if a field name is allowed for ordering.

        Args:
            key: The field name to validate.

        Raises:
            ValueError: If the field is not in VALID_ORDER_FIELDS.
        """
        if key not in self.VALID_ORDER_FIELDS:
            raise ValueError(f"Invalid Field {key}. Fields: {', '.join(self.VALID_ORDER_FIELDS)}")

    def _safe_resolve(self, path: Path) -> Path:
        """
        Resolves a path and ensures it is within the root directory.

        Args:
            path: The path to resolve.

        Returns:
            The resolved absolute Path.

        Raises:
            PermissionError: If the resolved path is outside the root directory.
        """
        path = self._normalize_path(path)
        resolved = path.resolve()
        try:
            resolved.relative_to(self._root_dir)
        except ValueError:
            raise PermissionError("Access denied.")
        return resolved

    def _order_by_key_normalize(self, key: str) -> tuple:
        """
        Parses an order_by key into field name and sort direction.

        A leading '-' indicates descending order.

        Args:
            key: The order_by string, e.g. 'name' or '-name'.

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
    
    def iter_directory(self, 
                       path: Path, 
                       recursive: bool = False) -> Generator[dict, None, None]:
        """
        Iter through a directory given by path.

        Args:
            path: indicates wich directory to iterate.
            recursive: indicates if must iterate through directories recursively.

        Yield:
            A dict for each file/folder item with the following structure:
            {
                'name': str,
                'path': str,
                'type': 'file' | 'directory',
                'size': int,
                'modified_at': str,
                'extension': str
            }
            
        Raises:
            FileNotFoundError: If the resolved path isn't a file/folder.
            NotADirectoryError: If the resolved path isn't a directory.   

        Example:
            >>> data = list(self.iter_directory(Path('example')), recursive=True)
        """
        resolved_path = self._safe_resolve(path)
        if not resolved_path.exists():
            raise FileNotFoundError("Path does not exists.")
        if not resolved_path.is_dir():
            raise NotADirectoryError("Path is not a directory.")
        
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
                try:
                    stats = child.stat()
                    is_dir = child.is_dir()
                except (PermissionError, FileNotFoundError):
                    continue
                datetime_child = datetime.fromtimestamp(stats.st_mtime)
                datetime_child = datetime_child.strftime(self.DT_TEMPLATE)
                yield {
                    'name': child.name,
                    'path': str(child.relative_to(self._root_dir)),
                    'type': 'directory' if is_dir else 'file',
                    'size': stats.st_size,
                    'modified_at': datetime_child,
                    'extension': child.suffix.lstrip('.')
                }
                
                if recursive and is_dir:
                    resolved_child = self._safe_resolve(child)
                    if resolved_child not in visited:
                        stack.append(resolved_child)
              
    def search(
            self, 
            name: str | None = None,
            extension: str | None = None,
            min_size: int | None = None,
            max_size: int | None = None,
            contains: str | None = None, 
            recursive: bool = False,
            path: Path | None = None) -> Generator[dict, None, None]:
            """
            Search for files and directories within the root directory using multiple filters.

            This method performs a lazy search (generator-based), yielding results as they are found,
            without loading all data into memory.

            Filters are combined using logical AND (all conditions must be satisfied).

            Args:
                name: Case-insensitive substring match against the file/directory name.
                extension: Exact match for file extension (case-insensitive, with or without leading dot).
                min_size: Minimum file size in bytes (inclusive).
                max_size: Maximum file size in bytes (inclusive).
                contains: Case-insensitive substring match across all fields (name, path, type, size, etc.).
                path: Directory to search in. If None, defaults to the root directory.

            Yields:
                dict: A dictionary representing a file or directory with the following structure:
                    {
                        'name': str,
                        'path': str,
                        'type': 'file' | 'directory',
                        'size': int,
                        'modified_at': str,
                        'extension': str
                    }

            Raises:
                PermissionError: If the path is outside the root directory.
                FileNotFoundError: If the path does not exist.
                NotADirectoryError: If the path is not a directory.
                ValueError: If min_size is greater than max_size.

            Example:
                >>> fm = FileManager('/home/user/documents')
                >>> list(fm.search(name="report"))
                >>> list(fm.search(extension="pdf", min_size=1000))
                >>> list(fm.search(name="log", contains="2024", path=Path("logs")))
            """
            path = path or Path('.')
            
            predicates = []
            
            if name:
                name_lower = name.lower()
                predicates.append(lambda item: name_lower in item["name"].lower())

            if extension:
                ext_lower = extension.lower().lstrip(".")
                predicates.append(lambda item: item["extension"].lower() == ext_lower)

            if min_size is not None:
                predicates.append(lambda item: item["size"] >= min_size)

            if max_size is not None:
                predicates.append(lambda item: item["size"] <= max_size)

            if contains:
                contains_lower = contains.lower()
                predicates.append(
                    lambda item: any(contains_lower in str(v).lower() for v in item.values())
                )
                
            if min_size and max_size:
                if min_size > max_size:
                    raise ValueError('Minimum size must be lower than maximum size.') 
            
            for item in self.iter_directory(path, recursive):
                if all(pred(item) for pred in predicates):
                    yield item

    def list_directory(self, 
                       path: Path, 
                       recursive: bool = False, 
                       order_by: str | None = None) -> dict:
        """
        Lists the contents of a directory within the root.

        Args:
            path: The directory path to list. Can be relative to root or absolute.
            order_by: Optional field to sort results by. Prefix with '-' for descending.
                      Valid fields: name, path, type, size, modified_at, extension.

        Returns:
            A dict with the following structure:
            {
                'total': int,
                'data': [
                    {
                        'name': str,
                        'path': str,
                        'type': 'file' | 'directory',
                        'size': int,
                        'modified_at': str,
                        'extension': str
                    },
                    ...
                ]
            }

        Raises:
            PermissionError: If the path is outside the root directory.
            FileNotFoundError: If the path does not exist.
            NotADirectoryError: If the path is not a directory.
            ValueError: If order_by field is invalid.

        Example:
            >>> fm = FileManager('/home/victor/documents')
            >>> fm.list_directory(Path('.'))
            >>> fm.list_directory(Path('.'), order_by='-size')
        """
        data = list(self.iter_directory(path, recursive))

        if order_by:
            field, reverse = self._order_by_key_normalize(order_by)
            self._is_key_valid(field)
            data = sorted(
                data,
                key=lambda item: (
                    (item.get(field) is None), 
                    (item.get(field) or 0) if field == 'size' 
                    else (item.get(field) or '')
                ),
                reverse=reverse
            )

        return {
            'total': len(data),
            'data': data
        }
    
if __name__ == '__main__':
    fm = FileManager(Path.cwd())