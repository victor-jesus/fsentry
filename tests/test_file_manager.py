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
        
class TestSymbolicLinks:
    @pytest.fixture
    def symlink_structure(self, tmp_path):
        real_folder = tmp_path / "real_folder"
        real_folder.mkdir()
        real_file = real_folder / "real_file.txt"
        real_file.write_text("hello")

        (tmp_path / "link_to_folder").symlink_to(real_folder)
        (tmp_path / "link_to_file.txt").symlink_to(real_file)

        return tmp_path

    def test_symlinks_excluded_by_default(self, symlink_structure):
        fm = FileManager(symlink_structure)
        result = fm.list_directory(Path("."))
        names = [item["name"] for item in result["data"]]

        assert "link_to_folder" not in names
        assert "link_to_file.txt" not in names
        assert "real_folder" in names

    def test_symlinks_included_when_allowed(self, symlink_structure):
        fm = FileManager(symlink_structure)
        result = fm.list_directory(Path("."), allow_symbolic_link=True)
        names = [item["name"] for item in result["data"]]

        assert "link_to_folder" in names
        assert "link_to_file.txt" in names

    def test_symlink_metadata_is_symbolic_link_true(self, symlink_structure):
        fm = FileManager(symlink_structure)
        result = fm.list_directory(Path("."), allow_symbolic_link=True)
        links = {item["name"]: item for item in result["data"]}

        assert links["link_to_folder"]["is_symbolic_link"] is True
        assert links["link_to_file.txt"]["is_symbolic_link"] is True
        assert links["real_folder"]["is_symbolic_link"] is False

    def test_symlink_dir_reported_as_directory(self, symlink_structure):
        fm = FileManager(symlink_structure)
        result = fm.list_directory(Path("."), allow_symbolic_link=True)
        links = {item["name"]: item for item in result["data"]}

        assert links["link_to_folder"]["type"] == "directory"
        assert links["link_to_file.txt"]["type"] == "file"

    def test_symlink_outside_root_raises_permission_error(self, tmp_path):
        outside = tmp_path.parent / "outside_file.txt"
        outside.write_text("secret")
        (tmp_path / "evil_link.txt").symlink_to(outside)

        fm = FileManager(tmp_path)
        result = fm.list_directory(Path("."))
        assert result["total"] == 0

        result_with_links = fm.list_directory(Path("."), allow_symbolic_link=True)
        names = [item["name"] for item in result_with_links["data"]]
        assert "evil_link.txt" not in names

    def test_search_finds_symlinked_file_when_allowed(self, symlink_structure):
        fm = FileManager(symlink_structure)
        result = list(fm.search(name="link_to_file", allow_symbolic_link=True))
        assert len(result) == 1
        assert result[0]["is_symbolic_link"] is True

    def test_search_excludes_symlinks_by_default(self, symlink_structure):
        fm = FileManager(symlink_structure)
        result = list(fm.search(name="link"))
        assert result == []


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
        (tmp_path / 'report.txt').touch()
        (tmp_path / 'outro.txt').touch()
        fm = FileManager(tmp_path)
        result = list(fm.search(name='repo'))
        assert len(result) == 1
        assert result[0]['name'] == 'report.txt'

    def test_search_by_name_is_case_insensitive(self, tmp_path):
        (tmp_path / 'report.txt').touch()
        fm = FileManager(tmp_path)
        result = list(fm.search(name='repo'))
        assert len(result) == 1

    def test_search_returns_empty_if_no_match(self, tmp_path):
        (tmp_path / 'file.txt').touch()
        fm = FileManager(tmp_path)
        result = list(fm.search(name='notvalid'))
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
        (tmp_path / 'report.txt').touch()
        (tmp_path / 'other.txt').touch()
        fm = FileManager(tmp_path)
        result = list(fm.search(contains='repo'))
        assert len(result) == 1

    def test_search_combined_filters(self, tmp_path):
        (tmp_path / 'report.pdf').write_text('a' * 500)
        (tmp_path / 'report.txt').write_text('a')
        (tmp_path / 'other.pdf').write_text('a' * 500)
        fm = FileManager(tmp_path)
        result = list(fm.search(name='report', extension='pdf'))
        assert len(result) == 1
        assert result[0]['name'] == 'report.pdf'

    def test_search_outside_root_raises_permission_error(self, tmp_path):
        fm = FileManager(tmp_path)
        with pytest.raises(PermissionError):
            list(fm.search(name='test', path=Path('/etc')))

    def test_search_returns_generator(self, tmp_path):
        fm = FileManager(tmp_path)
        result = fm.search(name='test')
        assert isinstance(result, Generator)
        
class TestSearchRecursive:
    def test_search_recursive_finds_nested_file(self, tmp_path):
        nested = tmp_path / "folder" / "sub"
        nested.mkdir(parents=True)
        (nested / "report.txt").touch()
        fm = FileManager(tmp_path)
        result = list(fm.search(name="report", recursive=True))
        assert len(result) == 1
        assert result[0]["name"] == "report.txt"

    def test_search_non_recursive_ignores_nested_file(self, tmp_path):
        nested = tmp_path / "folder"
        nested.mkdir()
        (nested / "report.txt").touch()
        fm = FileManager(tmp_path)
        result = list(fm.search(name="report", recursive=False))
        assert result == []

    def test_search_recursive_finds_in_multiple_levels(self, tmp_path):
        (tmp_path / "a").mkdir()
        (tmp_path / "a" / "b").mkdir()
        (tmp_path / "a" / "b" / "deep.txt").touch()
        (tmp_path / "shallow.txt").touch()
        fm = FileManager(tmp_path)
        result = list(fm.search(name=".txt", recursive=True))
        names = [item["name"] for item in result]
        assert "deep.txt" in names
        assert "shallow.txt" in names

    def test_search_recursive_returns_directories_too(self, tmp_path):
        (tmp_path / "reports").mkdir()
        (tmp_path / "reports" / "sub_reports").mkdir()
        fm = FileManager(tmp_path)
        result = list(fm.search(name="reports", recursive=True))
        names = [item["name"] for item in result]
        assert "reports" in names
        assert "sub_reports" in names


class TestSearchHiddenFiles:
    def test_search_excludes_hidden_files_by_default(self, tmp_path):
        (tmp_path / ".hidden.txt").touch()
        (tmp_path / "visible.txt").touch()
        fm = FileManager(tmp_path)
        result = list(fm.search())
        names = [item["name"] for item in result]
        assert ".hidden.txt" not in names
        assert "visible.txt" in names

    def test_search_includes_hidden_files_when_enabled(self, tmp_path):
        (tmp_path / ".hidden.txt").touch()
        fm = FileManager(tmp_path)
        result = list(fm.search(hidden_files=True))
        names = [item["name"] for item in result]
        assert ".hidden.txt" in names

    def test_search_hidden_combined_with_name(self, tmp_path):
        (tmp_path / ".secret_report.txt").touch()
        (tmp_path / "public_report.txt").touch()
        fm = FileManager(tmp_path)
        result = list(fm.search(name="report", hidden_files=True))
        names = [item["name"] for item in result]
        assert ".secret_report.txt" in names
        assert "public_report.txt" in names


class TestSearchSizeBoundary:
    def test_search_min_size_inclusive(self, tmp_path):
        (tmp_path / "exact.txt").write_text("a" * 100)
        fm = FileManager(tmp_path)
        result = list(fm.search(min_size=100))
        assert len(result) == 1
        assert result[0]["name"] == "exact.txt"

    def test_search_max_size_inclusive(self, tmp_path):
        (tmp_path / "exact.txt").write_text("a" * 100)
        fm = FileManager(tmp_path)
        result = list(fm.search(max_size=100))
        assert len(result) == 1
        assert result[0]["name"] == "exact.txt"

    def test_search_size_range(self, tmp_path):
        (tmp_path / "small.txt").write_text("a" * 10)
        (tmp_path / "medium.txt").write_text("a" * 500)
        (tmp_path / "large.txt").write_text("a" * 2000)
        fm = FileManager(tmp_path)
        result = list(fm.search(min_size=100, max_size=1000))
        assert len(result) == 1
        assert result[0]["name"] == "medium.txt"

    def test_search_min_size_zero_returns_all(self, tmp_path):
        (tmp_path / "file.txt").touch()
        fm = FileManager(tmp_path)
        result = list(fm.search(min_size=0))
        assert len(result) == 1


class TestSearchPath:
    def test_search_in_subdirectory(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "target.txt").touch()
        (tmp_path / "other.txt").touch()
        fm = FileManager(tmp_path)
        result = list(fm.search(path=Path("sub")))
        assert len(result) == 1
        assert result[0]["name"] == "target.txt"

    def test_search_path_not_found_raises(self, tmp_path):
        fm = FileManager(tmp_path)
        with pytest.raises(FileNotFoundError):
            list(fm.search(path=Path("nao_existe")))

    def test_search_path_is_not_dir_raises(self, tmp_path):
        (tmp_path / "file.txt").touch()
        fm = FileManager(tmp_path)
        with pytest.raises(NotADirectoryError):
            list(fm.search(path=Path("file.txt")))


class TestSearchSymlinks:
    @pytest.fixture
    def symlink_structure(self, tmp_path):
        real = tmp_path / "real"
        real.mkdir()
        (real / "report.txt").write_text("hello")
        (tmp_path / "link_to_report.txt").symlink_to(real / "report.txt")
        return tmp_path

    def test_search_excludes_symlinks_by_default(self, symlink_structure):
        fm = FileManager(symlink_structure)
        result = list(fm.search(name="link_to_report"))
        assert result == []

    def test_search_includes_symlinks_when_allowed(self, symlink_structure):
        fm = FileManager(symlink_structure)
        result = list(fm.search(name="link_to_report", allow_symbolic_link=True))
        assert len(result) == 1
        assert result[0]["is_symbolic_link"] is True

    def test_search_symlink_outside_root_is_ignored(self, tmp_path):
        outside = tmp_path.parent / "outside.txt"
        outside.write_text("secret")
        (tmp_path / "evil_link.txt").symlink_to(outside)
        fm = FileManager(tmp_path)
        result = list(fm.search(allow_symbolic_link=True))
        names = [item["name"] for item in result]
        assert "evil_link.txt" not in names


class TestSearchNoFilters:
    def test_search_no_filters_returns_all(self, tmp_path):
        (tmp_path / "a.txt").touch()
        (tmp_path / "b.pdf").touch()
        (tmp_path / "folder").mkdir()
        fm = FileManager(tmp_path)
        result = list(fm.search())
        assert len(result) == 3

    def test_search_empty_directory_returns_empty(self, tmp_path):
        fm = FileManager(tmp_path)
        result = list(fm.search())
        assert result == []
    