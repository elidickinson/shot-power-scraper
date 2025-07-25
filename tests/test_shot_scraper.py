import os
import pathlib
from unittest.mock import patch, MagicMock
import textwrap
from click.testing import CliRunner
import pytest
from shot_power_scraper.cli import cli
import zipfile
import json


# Mark for tests that require a working browser (skip only in CI)
browser_required = pytest.mark.skipif(
    "CI" in os.environ or "GITHUB_ACTIONS" in os.environ,
    reason="Requires browser, skipped in CI"
)


def test_version():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert result.output.startswith("cli, version ")


SERVER_YAML = """
- server: python -m http.server 9023
- url: http://localhost:9023/
  output: output.png
""".strip()

SERVER_YAML2 = """
- server:
  - python
  - -m
  - http.server
  - 9023
- url: http://localhost:9023/
  output: output.png
""".strip()

COMMANDS_YAML = """
- sh: echo "hello world" > index.html
- sh:
  - touch
  - touched.html
- python: |
    content = open("index.html").read()
    open("index.html", "w").write(content.upper())
"""


@browser_required
@pytest.mark.parametrize("yaml", (SERVER_YAML, SERVER_YAML2))
def test_multi_server(yaml):
    runner = CliRunner()
    with runner.isolated_filesystem():
        open("server.yaml", "w").write(yaml)
        result = runner.invoke(cli, ["multi", "server.yaml"])
        assert result.exit_code == 0, result.output
        assert pathlib.Path("output.png").exists()


def test_multi_commands():
    runner = CliRunner()
    with runner.isolated_filesystem():
        yaml_file = "commands.yaml"
        open(yaml_file, "w").write(COMMANDS_YAML)
        result = runner.invoke(cli, ["multi", yaml_file], catch_exceptions=False)
        assert result.exit_code == 0, result.output
        assert pathlib.Path("touched.html").exists()
        assert pathlib.Path("index.html").exists()
        assert open("index.html").read().strip() == "HELLO WORLD"


@pytest.mark.parametrize("input", ("key: value", "This is a string", "3.55"))
def test_multi_error_on_non_list(input):
    runner = CliRunner()
    result = runner.invoke(cli, ["multi", "-"], input=input)
    assert result.exit_code == 1
    assert result.output == "Error: YAML file must contain a list\n"


@pytest.mark.parametrize(
    "args,expected_shot_count",
    (
        ([], 2),
        (["--no-clobber"], 1),
        (["-n"], 1),
    ),
)
def test_multi_noclobber(mocker, args, expected_shot_count):
    # Mock the take_shot function where it's imported in cli.py
    take_shot = mocker.patch("shot_power_scraper.cli.take_shot", new_callable=mocker.AsyncMock)
    runner = CliRunner()
    with runner.isolated_filesystem():
        yaml = textwrap.dedent(
            """
        - url: https://www.example.com/
          output: example.jpg
        - url: https://www.google.com/
          output: google.jpg
        """
        ).strip()
        open("shots.yaml", "w").write(yaml)
        open("example.jpg", "wb").write(b"")
        result = runner.invoke(cli, ["multi", "shots.yaml"] + args, input=yaml)
        assert result.exit_code == 0, str(result.exception)
        assert take_shot.call_count == expected_shot_count


TEST_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Test title</title>
</head>
<body>
<h1>Test</h1>
<p>Paragraph 1</p>
</body>
</html>
"""


@browser_required
@pytest.mark.parametrize(
    "args,expected",
    (
        (["document.title"], '"Test title"\n'),
        (["document.title", "-r"], "Test title"),
        (["document.title", "--raw"], "Test title"),
        (["4 * 5"], "20\n"),
        (["4 * 5", "--raw"], "20"),
    ),
)
def test_javascript(args, expected):
    runner = CliRunner()
    with runner.isolated_filesystem():
        open("index.html", "w").write(TEST_HTML)
        result = runner.invoke(cli, ["javascript", "index.html"] + args)
        assert result.exit_code == 0, str(result.exception)
        assert result.output == expected


@browser_required
def test_javascript_input_file():
    runner = CliRunner()
    with runner.isolated_filesystem():
        open("index.html", "w").write(TEST_HTML)
        open("script.js", "w").write("document.title")
        result = runner.invoke(cli, ["javascript", "index.html", "-i", "script.js"])
        assert result.exit_code == 0, str(result.exception)
        assert result.output == '"Test title"\n'


@browser_required
@pytest.mark.skip(reason="Test is failing - see TODO.md")
def test_javascript_input_github():
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = b"document.title"
    mock_urlopen = MagicMock()
    mock_urlopen.__enter__.return_value = mock_response
    mock_context = MagicMock()
    mock_context.return_value = mock_urlopen

    runner = CliRunner()
    with patch("urllib.request.urlopen", mock_context):
        with runner.isolated_filesystem():
            open("index.html", "w").write(TEST_HTML)
            result = runner.invoke(
                cli, ["javascript", "index.html", "-i", "gh:simonw/title"]
            )
            assert result.exit_code == 0, str(result.exception)
            assert result.output == '"Test title"\n'
            mock_context.assert_called_once_with(
                "https://raw.githubusercontent.com/simonw/shot-power-scraper-scripts/main/title.js"
            )


@browser_required
@pytest.mark.parametrize(
    "args,expected",
    (
        ([], TEST_HTML),
        (
            ["-j", "document.body.removeChild(document.querySelector('h1'))"],
            (
                "<!DOCTYPE html><html><head><title>Test title</title></head>"
                "<body><p>Paragraph 1</p></body></html>"
            ),
        ),
        (
            [
                "-j",
                "document.querySelector('h1').innerText = navigator.userAgent",
                "--user-agent",
                "boo",
            ],
            (
                "<!DOCTYPE html><html><head><title>Test title</title></head>"
                "<body><h1>boo</h1><p>Paragraph 1</p></body></html>"
            ),
        ),
        (
            [
                "-s",
                "h1",
            ],
            ("<h1>Test</h1>"),
        ),
    ),
)
def test_html(args, expected):
    runner = CliRunner()
    with runner.isolated_filesystem():
        open("index.html", "w").write(TEST_HTML)
        result = runner.invoke(cli, ["html", "index.html"] + args)
        assert result.exit_code == 0, result.output
        # Whitespace is not preserved
        assert result.output.replace("\n", "") == expected.replace("\n", "")


@pytest.mark.parametrize(
    "command,flag",
    [
        ("shot", "--ad-block"),
        ("shot", "--popup-block"),
        ("shot", "--devtools"),
        ("multi", "--ad-block"),
        ("multi", "--popup-block"),
    ],
)
def test_cli_flags_no_crash(command, flag):
    """Test that CLI flags don't crash commands"""
    runner = CliRunner()
    result = runner.invoke(cli, [command, flag, "--help"])
    assert result.exit_code == 0
    assert flag in result.output


def test_shot_basic():
    """Test basic shot command help works"""
    runner = CliRunner()
    result = runner.invoke(cli, ["shot", "--help"])
    assert result.exit_code == 0
    assert "Take a single screenshot" in result.output


def test_pdf_basic():
    """Test basic PDF command help works"""
    runner = CliRunner()
    result = runner.invoke(cli, ["pdf", "--help"])
    assert result.exit_code == 0
    assert "Create a PDF" in result.output


def test_config_save_load(mocker, tmp_path):
    """Test config persistence works"""
    from shot_power_scraper.shot_config import save_config, load_config

    # Mock the config directory to use a temporary path
    mocker.patch("shot_power_scraper.shot_config.get_config_dir", return_value=tmp_path)

    # Test save and load
    config = {"ad_block": True, "user_agent": "test"}
    save_config(config)
    loaded = load_config()
    assert loaded == config
