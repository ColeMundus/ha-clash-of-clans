"""Reader-facing image assets must not depend on third-party badge uptime."""

import re
from pathlib import Path
from xml.etree import ElementTree


def test_readme_badges_are_repository_local():
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text()
    badges = re.findall(r"\[!\[[^\]]+\]\(([^)]+)\)\]", readme)
    assert len(badges) == 4
    for path in badges:
        assert path.startswith("docs/badges/")
        svg = ElementTree.parse(root / path).getroot()
        assert svg.tag.endswith("svg")
        assert svg.attrib["role"] == "img"
        assert svg.attrib["aria-label"]
        assert not list(svg.iter("{http://www.w3.org/2000/svg}script"))


def test_readme_screenshots_resolve_without_embedded_metadata():
    from PIL import Image

    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text()
    screenshots = re.findall(r"!\[[^\]]+\]\((docs/images/[^)]+)\)", readme)
    assert screenshots == ["docs/images/setup.png"]
    for name in screenshots:
        with Image.open(root / name) as image:
            assert image.format == "PNG"
            assert 256 <= image.width <= 1600
            assert 256 <= image.height <= 2000
            assert not image.info
            image.verify()
