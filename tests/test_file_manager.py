import pytest
from pathlib import Path
from filemanager import FileManager

class TestFileManagerInit:
    def test_raises_if_root_is_not_a_directory(self, tmp_path):
        (tmp_path / 'test.txt').touch()
        with pytest.raises(NotADirectoryError):
            FileManager(tmp_path / 'test.txt')

class TestListDirectory:
    def test_valid(self, tmp_path):
        (tmp_path / 'docs').mkdir()
        fm = FileManager(tmp_path)
        result = fm.list_directory(Path('.'))
        assert result['total'] == 1
        assert result['data'][0]['name'] == 'docs'

    def test_empty_directory(self, tmp_path):
        (tmp_path / 'docs').mkdir()
        fm = FileManager(tmp_path)
        result = fm.list_directory(Path(tmp_path / 'docs'))
        assert result['total'] == 0

    def test_raises_if_path_not_found(self, tmp_path):
        fm = FileManager(tmp_path)
        with pytest.raises(FileNotFoundError):
            fm.list_directory(Path('nao_existe'))


class TestListDirectorySecurity:
    def test_path_traversal_raises_permission_error(self, tmp_path):
        fm = FileManager(tmp_path)
        with pytest.raises(PermissionError):
            fm.list_directory(Path('../../docs'))

    def test_absolute_path_outside_root_raises_permission_error(self, tmp_path):
        fm = FileManager(tmp_path)
        with pytest.raises(PermissionError):
            fm.list_directory(Path('/etc'))


class TestListDirectoryOrderBy:
    def test_invalid_order_by_raises_key_error(self, tmp_path):
        fm = FileManager(tmp_path)
        with pytest.raises(ValueError):
            fm.list_directory(Path('.'), 'invalid')

    def test_valid_order_by(self, tmp_path):
        (tmp_path / "b_arquivo.txt").touch()
        (tmp_path / "a_arquivo.txt").touch()
        fm = FileManager(tmp_path)
        result = fm.list_directory(Path('.'), 'name')
        assert isinstance(result, dict)
        assert 'total' in result
        assert 'data' in result
        names = [item['name'] for item in result['data']]
        assert names == ['a_arquivo.txt', 'b_arquivo.txt']

    def test_valid_order_by_reverse(self, tmp_path):
        (tmp_path / "b_arquivo.txt").touch()
        (tmp_path / "a_arquivo.txt").touch()
        fm = FileManager(tmp_path)
        result = fm.list_directory(Path('.'), '-name')
        assert isinstance(result, dict)
        assert 'total' in result
        assert 'data' in result
        names = [item['name'] for item in result['data']]
        assert names == ['b_arquivo.txt', 'a_arquivo.txt']