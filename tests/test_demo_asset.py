from pathlib import Path

from PIL import Image


def test_readme_demo_is_real_and_animated(repo_root: Path) -> None:
    demo = repo_root / "docs" / "assets" / "witness-demo.gif"
    transcript = repo_root / "docs" / "assets" / "demo-transcript.txt"
    assert demo.is_file() and demo.stat().st_size > 10_000
    assert transcript.is_file()
    with Image.open(demo) as image:
        assert getattr(image, "n_frames", 1) >= 4
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    assert "![Witness real browser QA demo](docs/assets/witness-demo.gif)" in readme
    assert "placeholder" not in readme.lower()
