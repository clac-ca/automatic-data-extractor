from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
APP_DIR = BACKEND_DIR / "app"
EXPECTED_APP_DIRS = {"api", "features", "shared", "web"}
EXPECTED_APP_FILES = {"__init__.py", "main.py"}


def _list_dirs(path: Path) -> set[str]:
    return {item.name for item in path.iterdir() if item.is_dir() and item.name != "__pycache__"}


def _list_files(path: Path) -> set[str]:
    return {
        item.name
        for item in path.iterdir()
        if item.is_file() and not item.name.endswith(".pyc")
    }


def test_backend_app_directory_layout() -> None:
    """Contract: backend/app must retain the expected directory skeleton."""
    app_files = _list_files(APP_DIR)
    app_dirs = _list_dirs(APP_DIR)

    missing_files = EXPECTED_APP_FILES - app_files
    assert not missing_files, f"backend/app is missing files: {sorted(missing_files)}"

    unexpected_dirs = app_dirs - EXPECTED_APP_DIRS
    missing_dirs = EXPECTED_APP_DIRS - app_dirs
    assert not unexpected_dirs, f"Unexpected directories in backend/app: {sorted(unexpected_dirs)}"
    assert not missing_dirs, f"Missing directories in backend/app: {sorted(missing_dirs)}"

    _assert_api_layout()
    _assert_shared_layout()
    _assert_web_layout()
    _assert_feature_packages()


def _assert_api_layout() -> None:
    api_dir = APP_DIR / "api"
    api_files = _list_files(api_dir)
    api_dirs = _list_dirs(api_dir)

    assert "__init__.py" in api_files, "backend/app/api must expose __init__.py"
    assert api_dirs == {"v1"}, f"backend/app/api should only contain 'v1', found {sorted(api_dirs)}"


def _assert_shared_layout() -> None:
    shared_dir = APP_DIR / "shared"
    shared_files = _list_files(shared_dir)
    shared_dirs = _list_dirs(shared_dir)

    assert "__init__.py" in shared_files, "backend/app/shared must expose __init__.py"
    expected_shared_dirs = {"core", "db", "repositories"}
    assert (
        shared_dirs == expected_shared_dirs
    ), f"backend/app/shared should contain {sorted(expected_shared_dirs)}, found {sorted(shared_dirs)}"


def _assert_web_layout() -> None:
    web_dir = APP_DIR / "web"
    web_dirs = _list_dirs(web_dir)
    assert web_dirs == {"static"}, f"backend/app/web should only contain 'static', found {sorted(web_dirs)}"

    static_dir = web_dir / "static"
    static_files = _list_files(static_dir)
    expected_static_files = {"index.html", "favicon.ico"}
    missing_static = expected_static_files - static_files
    assert not missing_static, f"backend/app/web/static missing files: {sorted(missing_static)}"


def _assert_feature_packages() -> None:
    features_dir = APP_DIR / "features"
    feature_files = _list_files(features_dir)
    assert "__init__.py" in feature_files, "backend/app/features must expose __init__.py"

    missing = []
    for feature_dir in features_dir.iterdir():
        if not feature_dir.is_dir() or feature_dir.name.startswith("__"):
            continue
        for required_module in ("__init__.py", "router.py"):
            if not (feature_dir / required_module).exists():
                missing.append((feature_dir.name, required_module))

    assert not missing, f"Feature packages missing modules: {missing}"
