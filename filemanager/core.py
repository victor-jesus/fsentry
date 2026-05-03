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
    
    def iter_directory(self, path: Path) -> Generator[dict, None, None]:
        """
        Iter through a directory given by path.

        Args:
            path: indicates wich directory to iterate.

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
            >>> data = list(self.iter_directory(Path('example')))
        """
        resolved_path = self._safe_resolve(path)
        if not resolved_path.exists():
            raise FileNotFoundError("Path does not exists.")
        if not resolved_path.is_dir():
            raise NotADirectoryError("Path is not a directory.")
        
        for child in resolved_path.iterdir():
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

    def list_directory(self, path: Path, order_by: str | None = None) -> dict:
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
        data = list(self.iter_directory(path))

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
    
    def search(self, value: str, keys: list[str] | None = None, path: Path | None = None) -> Generator[dict, None, None]:
        """
        Search for files and directories matching a value within the root.

        Performs a case-insensitive partial match against all fields or specific fields.

        Args:
            value: The search term to match against.
            keys: Optional list of fields to search in. If None, searches all fields.
                Valid fields: name, path, type, size, modified_at, extension.
            path: Optional directory to search in. Defaults to root directory.

        Yield:
            A dict for each matching item with the following structure:
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
            ValueError: If any key in keys is invalid.

        Example:
            >>> fm = FileManager('/home/victor/documents')
            >>> list(fm.search('report'))
            >>> list(fm.search('report', keys=['name']))
            >>> list(fm.search('report', keys=['name'], path=Path('work')))
        """
        path = path or self._root_dir
        value_lower = value.lower()    
        
        if keys is not None:
            for k in keys:
                self._is_key_valid(k)
                
            def match(item):
                return any(value_lower in str(item[k]).lower() for k in keys)
        else:
            def match(item):
                return any(value_lower in str(v).lower() for v in item.values())
        
        for item in self.iter_directory(path):
            if match(item):
                yield item
        
if __name__ == '__main__':
    fm = FileManager(Path.cwd())
    data = fm.search(keys=['name'], value="TEST")
    for item in data:
        print(item)
