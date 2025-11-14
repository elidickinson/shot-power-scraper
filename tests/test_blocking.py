import os
import sys
import pathlib
import pytest
from click.testing import CliRunner
from shot_power_scraper.cli import cli


# Mark for tests that require a working browser (skip only on Linux CI)
browser_required = pytest.mark.skipif(
    sys.platform.startswith('linux') and "CI" in os.environ,
    reason="Requires browser display, skipped on Linux CI"
)


@pytest.mark.parametrize(
    "command,args",
    [
        ("shot", ["--ad-block", "--help"]),

        ("shot", ["--paywall-block", "--help"]),
        ("multi", ["--ad-block", "--help"]),

        ("pdf", ["--ad-block", "--help"]),
        ("html", ["--ad-block", "--help"]),
        ("mhtml", ["--ad-block", "--help"]),
        ("javascript", ["--ad-block", "--help"]),
    ],
)
def test_blocking_flags_accepted(command, args):
    """Test that blocking flags are accepted by all commands"""
    runner = CliRunner()
    result = runner.invoke(cli, [command] + args)
    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert "--ad-block" in result.output or "help" in result.output


@browser_required
def test_ad_block_basic():
    """Test that --ad-block flag works without errors"""
    runner = CliRunner()
    with runner.isolated_filesystem():
        test_page = "test.html"
        with open(test_page, "w") as f:
            f.write("""
            <!DOCTYPE html>
            <html>
            <head><title>Test</title></head>
            <body>
                <h1>Clean Content</h1>
                <div class="ad-unit">Advertisement</div>
            </body>
            </html>
            """)

        result = runner.invoke(cli, [
            "shot", test_page,
            "--ad-block",
            "-o", "blocked.png"
        ])
        assert result.exit_code == 0, f"Command failed: {result.output}\nException: {result.exception}"
        assert os.path.exists("blocked.png")

        # Verify file was created
        file_size = os.path.getsize("blocked.png")
        assert file_size > 100, f"Screenshot file seems too small: {file_size} bytes"


@browser_required


@browser_required
def test_blocking_with_local_test_page():
    """Test blocking with the provided ad-popup-test.html page"""
    runner = CliRunner()

    # Use the test page from tests/pages directory
    test_page = pathlib.Path(__file__).parent / "pages" / "ad-popup-test.html"
    if not test_page.exists():
        pytest.skip("ad-popup-test.html not found")

    with runner.isolated_filesystem():
        # Test without blocking
        result = runner.invoke(cli, [
            "shot", str(test_page),
            "-o", "no_blocking.png",
            "-w", "800",
            "-h", "600"
        ])
        assert result.exit_code == 0, f"No blocking failed: {result.output}"
        assert os.path.exists("no_blocking.png")

        # Test with ad blocking only
        result = runner.invoke(cli, [
            "shot", str(test_page),
            "--ad-block",
            "-o", "ad_blocked.png",
            "-w", "800",
            "-h", "600"
        ])
        assert result.exit_code == 0, f"Ad blocking failed: {result.output}"
        assert os.path.exists("ad_blocked.png")

        # All screenshots should exist and have reasonable sizes
        no_block_size = os.path.getsize("no_blocking.png")
        ad_block_size = os.path.getsize("ad_blocked.png")

        assert no_block_size > 1000, "No blocking screenshot too small"
        assert ad_block_size > 1000, "Ad blocking screenshot too small"



@browser_required
def test_blocking_in_multi_shot():
    """Test that blocking works in multi-shot YAML"""
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Create test HTML
        with open("test.html", "w") as f:
            f.write("""
            <!DOCTYPE html>
            <html>
            <head><title>Test</title></head>
            <body>
                <h1>Content</h1>
                <div class="ad-unit">Ad</div>
            </body>
            </html>
            """)

        # Create YAML config
        yaml_content = """
        - url: test.html
          output: shot1.png
          width: 400
          height: 300
        """
        with open("multi.yaml", "w") as f:
            f.write(yaml_content)

        result = runner.invoke(cli, [
            "multi", "multi.yaml",
            "--ad-block"
        ])
        assert result.exit_code == 0, f"Multi with blocking failed: {result.output}"
        assert os.path.exists("shot1.png")


@browser_required
def test_paywall_block():
    """Test that --paywall-block flag works"""
    runner = CliRunner()
    with runner.isolated_filesystem():
        test_page = "test.html"
        with open(test_page, "w") as f:
            f.write("""
            <!DOCTYPE html>
            <html>
            <head><title>Test</title></head>
            <body><h1>Article</h1><p>Content</p></body>
            </html>
            """)

        result = runner.invoke(cli, [
            "shot", test_page,
            "--paywall-block",
            "-o", "paywall_test.png"
        ])
        assert result.exit_code == 0, f"Paywall blocking failed: {result.output}"
        assert os.path.exists("paywall_test.png")


@browser_required
def test_combined_blocking():
    """Test that ad-block, ublock-lists, and paywall-block work together"""
    runner = CliRunner()
    with runner.isolated_filesystem():
        test_page = "test.html"
        with open(test_page, "w") as f:
            f.write("""
            <!DOCTYPE html>
            <html>
            <head><title>Test</title></head>
            <body>
                <h1>Article</h1>
                <div class="ad-unit">Ad</div>
                <div id="cookieNotice">Cookie notice</div>
            </body>
            </html>
            """)

        result = runner.invoke(cli, [
            "shot", test_page,
            "--ad-block",
            "--paywall-block",
            "-o", "combined.png"
        ])
        assert result.exit_code == 0, f"Combined blocking failed: {result.output}"
        assert os.path.exists("combined.png")
