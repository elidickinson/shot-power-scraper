import pytest
from shot_power_scraper.utils import filename_for_url


@pytest.mark.quick
@pytest.mark.parametrize(
    "url,ext,expected",
    (
        ("https://datasette.io/", None, "datasette-io.png"),
        ("https://datasette.io/tutorials", "png", "datasette-io-tutorials.png"),
        (
            "https://datasette.io/-/versions.json",
            "jpg",
            "datasette-io---versions-json.jpg",
        ),
        ("/tmp/index.html", "png", "tmp-index-html.png"),
    ),
)
def test_filename_for_url(url, ext, expected):
    assert filename_for_url(url, ext) == expected


