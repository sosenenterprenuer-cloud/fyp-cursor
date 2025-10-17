import importlib.util
import pathlib

APP_PATH = pathlib.Path(__file__).resolve().parents[1] / 'app.py'
spec = importlib.util.spec_from_file_location('app_module', APP_PATH)
app_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app_module)  # type: ignore


def test_categorize_time():
    c = app_module.categorize_time
    assert c(9.99) == 'Fast'
    assert c(10.0) == 'Normal'
    assert c(20.0) == 'Normal'
    assert c(20.01) == 'Slow'
