import pytest
from pathlib import Path
from collections.abc import Generator
from filemanager import FileManager


class TestFileManagerInit:
    def test_raises_if_root_is_not_a_directory(self, tmp_path):
        (tmp_path / 'test.txt').touch()
        with pytest.raises(NotADirectoryError):
            FileManager(tmp_path / 'test.txt')

    def test_raises_if_root_does_not_exist(self, tmp_path):
        with pytest.raises(ValueError):
            FileManager(tmp_path / 'nao_existe')

    def test_accepts_string_as_root(self, tmp_path):
        fm = FileManager(str(tmp_path))
        assert fm._root_dir == tmp_path.resolve()

    def test_custom_dt_template(self, tmp_path):
        fm = FileManager(tmp_path, dt_template='%d/%m/%Y')
        assert fm.DT_TEMPLATE == '%d/%m/%Y'

    def test_custom_valid_order_fields(self, tmp_path):
        fm = FileManager(tmp_path, valid_order_fields={'name', 'size'})
        assert fm.VALID_ORDER_FIELDS == {'name', 'size'}


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

    def test_returns_correct_file_metadata(self, tmp_path):
        (tmp_path / 'test.txt').touch()
        fm = FileManager(tmp_path)
        result = fm.list_directory(Path('.'))
        item = result['data'][0]
        assert 'name' in item
        assert 'path' in item
        assert 'type' in item
        assert 'size' in item
        assert 'modified_at' in item
        assert 'extension' in item

    def test_distinguishes_files_and_directories(self, tmp_path):
        (tmp_path / 'folder').mkdir()
        (tmp_path / 'file.txt').touch()
        fm = FileManager(tmp_path)
        result = fm.list_directory(Path('.'))
        types = {item['name']: item['type'] for item in result['data']}
        assert types['folder'] == 'directory'
        assert types['file.txt'] == 'file'

    def test_returns_correct_extension(self, tmp_path):
        (tmp_path / 'file.txt').touch()
        fm = FileManager(tmp_path)
        result = fm.list_directory(Path('.'))
        assert result['data'][0]['extension'] == 'txt'

    def test_returns_empty_extension_for_directory(self, tmp_path):
        (tmp_path / 'folder').mkdir()
        fm = FileManager(tmp_path)
        result = fm.list_directory(Path('.'))
        assert result['data'][0]['extension'] == ''


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
    def test_invalid_order_by_raises_value_error(self, tmp_path):
        fm = FileManager(tmp_path)
        with pytest.raises(ValueError):
            fm.list_directory(Path('.'), order_by='invalid')

    def test_valid_order_by(self, tmp_path):
        (tmp_path / "b_arquivo.txt").touch()
        (tmp_path / "a_arquivo.txt").touch()
        fm = FileManager(tmp_path)
        result = fm.list_directory(Path('.'), order_by='name')
        assert isinstance(result, dict)
        assert 'total' in result
        assert 'data' in result
        names = [item['name'] for item in result['data']]
        assert names == ['a_arquivo.txt', 'b_arquivo.txt']

    def test_valid_order_by_reverse(self, tmp_path):
        (tmp_path / "b_arquivo.txt").touch()
        (tmp_path / "a_arquivo.txt").touch()
        fm = FileManager(tmp_path)
        result = fm.list_directory(Path('.'), order_by='-name')
        assert isinstance(result, dict)
        assert 'total' in result
        assert 'data' in result
        names = [item['name'] for item in result['data']]
        assert names == ['b_arquivo.txt', 'a_arquivo.txt']

    def test_order_by_size(self, tmp_path):
        small = tmp_path / 'small.txt'
        large = tmp_path / 'large.txt'
        small.write_text('a')
        large.write_text('a' * 1000)
        fm = FileManager(tmp_path)
        result = fm.list_directory(Path('.'), order_by='size')
        names = [item['name'] for item in result['data']]
        assert names == ['small.txt', 'large.txt']


class TestSearch:
    def test_search_by_name(self, tmp_path):
        (tmp_path / 'relatorio.txt').touch()
        (tmp_path / 'outro.txt').touch()
        fm = FileManager(tmp_path)
        result = list(fm.search(name='relat'))
        assert len(result) == 1
        assert result[0]['name'] == 'relatorio.txt'

    def test_search_by_name_is_case_insensitive(self, tmp_path):
        (tmp_path / 'Relatorio.txt').touch()
        fm = FileManager(tmp_path)
        result = list(fm.search(name='relat'))
        assert len(result) == 1

    def test_search_returns_empty_if_no_match(self, tmp_path):
        (tmp_path / 'arquivo.txt').touch()
        fm = FileManager(tmp_path)
        result = list(fm.search(name='naoexiste'))
        assert result == []

    def test_search_by_extension(self, tmp_path):
        (tmp_path / 'file.pdf').touch()
        (tmp_path / 'file.txt').touch()
        fm = FileManager(tmp_path)
        result = list(fm.search(extension='pdf'))
        assert len(result) == 1
        assert result[0]['extension'] == 'pdf'

    def test_search_by_extension_without_dot(self, tmp_path):
        (tmp_path / 'file.pdf').touch()
        fm = FileManager(tmp_path)
        result = list(fm.search(extension='.pdf'))
        assert len(result) == 1

    def test_search_by_min_size(self, tmp_path):
        (tmp_path / 'small.txt').write_text('a')
        (tmp_path / 'large.txt').write_text('a' * 1000)
        fm = FileManager(tmp_path)
        result = list(fm.search(min_size=500))
        assert len(result) == 1
        assert result[0]['name'] == 'large.txt'

    def test_search_by_max_size(self, tmp_path):
        (tmp_path / 'small.txt').write_text('a')
        (tmp_path / 'large.txt').write_text('a' * 1000)
        fm = FileManager(tmp_path)
        result = list(fm.search(max_size=10))
        assert len(result) == 1
        assert result[0]['name'] == 'small.txt'

    def test_search_min_size_greater_than_max_size_raises_value_error(self, tmp_path):
        fm = FileManager(tmp_path)
        with pytest.raises(ValueError):
            list(fm.search(min_size=1000, max_size=100))

    def test_search_by_contains(self, tmp_path):
        (tmp_path / 'relatorio.txt').touch()
        (tmp_path / 'outro.txt').touch()
        fm = FileManager(tmp_path)
        result = list(fm.search(contains='relat'))
        assert len(result) == 1

    def test_search_combined_filters(self, tmp_path):
        (tmp_path / 'relatorio.pdf').write_text('a' * 500)
        (tmp_path / 'relatorio.txt').write_text('a')
        (tmp_path / 'outro.pdf').write_text('a' * 500)
        fm = FileManager(tmp_path)
        result = list(fm.search(name='relatorio', extension='pdf'))
        assert len(result) == 1
        assert result[0]['name'] == 'relatorio.pdf'

    def test_search_outside_root_raises_permission_error(self, tmp_path):
        fm = FileManager(tmp_path)
        with pytest.raises(PermissionError):
            list(fm.search(name='test', path=Path('/etc')))

    def test_search_returns_generator(self, tmp_path):
        fm = FileManager(tmp_path)
        result = fm.search(name='test')
        assert isinstance(result, Generator)