from pathlib import Path
    
def normalize_path(path: Path, root_dir: Path) -> Path:
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
        path = root_dir / path
    return path

def is_key_valid(key: str, VALID_ORDER_FIELDS: set) -> None:
    """
    Validates if a field name is allowed for ordering.

    Args:
        key: The field name to validate.

    Raises:
        ValueError: If the field is not in VALID_ORDER_FIELDS.
    """
    if key not in VALID_ORDER_FIELDS:
        raise ValueError(f"Invalid Field {key}. Fields: {', '.join(VALID_ORDER_FIELDS)}")

def safe_resolve(path: Path, root_dir: Path) -> Path:
    """
    Resolves a path and ensures it is within the root directory.

    Args:
        path: The path to resolve.

    Returns:
        The resolved absolute Path.

    Raises:
        PermissionError: If the resolved path is outside the root directory.
    """
    path = normalize_path(path, root_dir)
    resolved = path.resolve()
    try:
        resolved.relative_to(root_dir)
    except ValueError:
        raise PermissionError("Access denied.")
    return resolved

def ensure_exists(resolved_path: Path):
    if not resolved_path.exists():
        raise FileNotFoundError("Path does not exists.")
    
def ensure_dir(resolved_path: Path):
    ensure_exists(resolved_path)
    if not resolved_path.is_dir():
        raise NotADirectoryError("Path is not a directory.")