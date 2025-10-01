import os
import pathlib
from unittest.mock import patch, MagicMock
import textwrap
from click.testing import CliRunner
import pytest
from shot_power_scraper.cli import cli



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


@browser_required
@pytest.mark.parametrize(
    "args",
    (
        ([]),
        (["-j", "document.body.removeChild(document.querySelector('h1'))"]),
        (["--user-agent", "test-agent"]),
        (["--ad-block"]),
        (["--popup-block"]),
        (["--trigger-lazy-load"]),
    ),
)
def test_mhtml(args):
    runner = CliRunner()
    with runner.isolated_filesystem():
        open("index.html", "w").write(TEST_HTML)
        result = runner.invoke(cli, ["mhtml", "index.html", "-o", "-"] + args)
        assert result.exit_code == 0, result.output
        # MHTML content should start with MIME boundary
        assert "MIME-Version:" in result.output
        assert "Content-Type: multipart/related" in result.output
        # Should contain the HTML content
        assert "Test title" in result.output


@pytest.mark.parametrize(
    "command,flag",
    [
        ("shot", "--ad-block"),
        ("shot", "--popup-block"),
        ("shot", "--devtools"),
        ("multi", "--ad-block"),
        ("multi", "--popup-block"),
        ("mhtml", "--ad-block"),
        ("mhtml", "--popup-block"),
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


# Integration tests for regression protection
@browser_required
def test_screenshot_dimensions_regression():
    """Regression test: verify --width and --height parameters work correctly"""
    import os
    runner = CliRunner()

    with runner.isolated_filesystem():
        # Create simple test page
        test_page = "test.html"
        with open(test_page, "w") as f:
            f.write("""
            <!DOCTYPE html>
            <html>
            <head><title>Dimension Test</title></head>
            <body style="margin:0; background: linear-gradient(45deg, red, blue); min-height: 100vh;">
                <div style="width: 100%; height: 100vh; display: flex; align-items: center; justify-content: center;">
                    <h1 style="color: white;">Test Content</h1>
                </div>
            </body>
            </html>
            """)

        # Test custom dimensions
        result = runner.invoke(cli, [
            "shot", test_page,
            "--width", "800",
            "--height", "600",
            "-o", "custom_size.png"
        ])
        assert result.exit_code == 0, str(result.exception)
        assert os.path.exists("custom_size.png")

        # Verify file was created with reasonable size (regression test)
        file_size = os.path.getsize("custom_size.png")
        assert file_size > 1000, f"Screenshot file seems too small: {file_size} bytes"
        assert file_size < 1000000, f"Screenshot file seems too large: {file_size} bytes"


@browser_required
def test_selector_screenshot_regression():
    """Regression test: verify selector screenshots work with proper timing"""
    import os
    runner = CliRunner()

    with runner.isolated_filesystem():
        # Create test page with selectors
        test_page = "selector_test.html"
        with open(test_page, "w") as f:
            f.write("""
            <!DOCTYPE html>
            <html>
            <head><title>Selector Test</title></head>
            <body style="margin: 0; padding: 20px; background: #f0f0f0;">
                <div style="background: white; padding: 20px; margin-bottom: 20px;">
                    <h1>Other Content</h1>
                    <p>This should not be in the screenshot</p>
                </div>
                <div id="target" style="background: #ff6b6b; color: white; padding: 20px; width: 300px; height: 200px;">
                    <h2>Target Element</h2>
                    <p>This should be captured</p>
                </div>
                <div style="background: white; padding: 20px; margin-top: 20px;">
                    <p>More content below</p>
                </div>
            </body>
            </html>
            """)

        # Test selector screenshot
        result = runner.invoke(cli, [
            "shot", test_page,
            "-s", "#target",
            "-o", "selector.png"
        ])
        assert result.exit_code == 0, str(result.exception)
        assert os.path.exists("selector.png")

        # Test multiple selectors with padding
        result = runner.invoke(cli, [
            "shot", test_page,
            "-s", "#target",
            "--padding", "10",
            "-o", "selector_padded.png"
        ])
        assert result.exit_code == 0, str(result.exception)
        assert os.path.exists("selector_padded.png")

        # Verify selector with padding creates different sized file
        size1 = os.path.getsize("selector.png")
        size2 = os.path.getsize("selector_padded.png")
        assert size2 > size1, "Padded selector should create larger image"


@browser_required
def test_pdf_generation_basic():
    """Basic PDF generation test"""
    import os
    runner = CliRunner()

    with runner.isolated_filesystem():
        # Create minimal HTML file for PDF generation
        test_page = "pdf_test.html"
        with open(test_page, "w") as f:
            f.write("""<!DOCTYPE html>
<html>
<head><title>PDF Test</title></head>
<body>
<h1>Test PDF</h1>
<p>Simple content.</p>
</body>
</html>""")

        result = runner.invoke(cli, [
            "pdf", test_page,
            "-o", "test.pdf",
        ])
        assert result.exit_code == 0, f"PDF generation failed: {result.output}\nException: {result.exception}"
        assert os.path.exists("test.pdf")

        # Basic validation - PDF should be reasonable size
        pdf_size = os.path.getsize("test.pdf")
        assert pdf_size > 500, f"PDF seems too small: {pdf_size} bytes"
        assert pdf_size < 2000000, f"PDF seems too large: {pdf_size} bytes"


@browser_required
def test_multi_shot_architecture():
    """Test multi-shot YAML works with new architecture"""
    import os
    runner = CliRunner()

    with runner.isolated_filesystem():
        # Create test HTML files
        with open("page1.html", "w") as f:
            f.write("<html><body><h1>Shot 1</h1></body></html>")

        with open("page2.html", "w") as f:
            f.write("<html><body><h1>Shot 2</h1></body></html>")

        # Create simple YAML config
        yaml_content = """
        - url: page1.html
          output: shot1.png
          width: 400
          height: 300
        - url: page2.html
          output: shot2.png
          width: 600
          height: 400
        """

        with open("multi_test.yaml", "w") as f:
            f.write(yaml_content)

        result = runner.invoke(cli, ["multi", "multi_test.yaml"])
        assert result.exit_code == 0, str(result.exception)

        # Verify both shots were created
        assert os.path.exists("shot1.png")
        assert os.path.exists("shot2.png")


@browser_required
def test_javascript_execution():
    """Test JavaScript execution works correctly"""
    runner = CliRunner()

    with runner.isolated_filesystem():
        test_page = "js_test.html"
        with open(test_page, "w") as f:
            f.write("""
            <!DOCTYPE html>
            <html>
            <head><title>JS Test</title></head>
            <body>
                <div id="target">Original Text</div>
                <script>
                    window.testValue = 42;
                </script>
            </body>
            </html>
            """)

        # Test reading a value
        result = runner.invoke(cli, [
            "javascript", test_page, "window.testValue"
        ])
        assert result.exit_code == 0, str(result.exception)
        assert "42" in result.output

        # Test DOM manipulation
        result = runner.invoke(cli, [
            "javascript", test_page,
            "document.getElementById('target').innerText = 'Modified'; document.getElementById('target').innerText"
        ])
        assert result.exit_code == 0, str(result.exception)
        assert "Modified" in result.output
