from pathlib import Path

import app as package
from app.main import create_app
from app.runtime import _version


PRODUCT_VERSION = "1.0.0"


def test_product_version_identity_is_consistent(fake_runtime):
    repository_root = Path(__file__).resolve().parents[2]
    runtime, *_ = fake_runtime
    application = create_app(runtime, refresh_on_startup=False, test_mode=True)

    assert (repository_root / "VERSION").read_text(encoding="utf-8").strip() == PRODUCT_VERSION
    assert package.__version__ == PRODUCT_VERSION
    assert _version() == package.__version__
    assert runtime.info()["version"] == package.__version__
    assert application.version == package.__version__
    assert application.openapi()["info"]["version"] == package.__version__
