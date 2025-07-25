import pytest
from shot_power_scraper.shot_config import ShotConfig


@pytest.mark.quick
class TestShotConfig:
    """Fast unit tests for ShotConfig functionality"""

    def test_basic_config_creation(self):
        """Test basic ShotConfig creation with minimal parameters"""
        config = ShotConfig({"url": "https://example.com"})
        assert config.url == "https://example.com"
        assert config.width == 1280  # default
        assert config.height == 720  # default

    def test_locals_pattern_filtering(self):
        """Test ShotConfig handles locals() pattern correctly"""
        # Simulate what happens in CLI commands
        url = "https://example.com"
        width = 1600
        height = 900
        retina = False
        scale_factor = None
        some_file_object = open(__file__, 'r')
        
        try:
            # This simulates the locals() call in CLI commands
            params = locals()
            config = ShotConfig(params)
            
            assert config.url == url
            assert config.width == width
            assert config.height == height
            assert config.scale_factor is None
        finally:
            some_file_object.close()

    def test_scale_factor_retina_validation(self):
        """Test scale factor and retina validation logic"""
        # Valid: retina only
        config = ShotConfig({"retina": True})
        assert config.scale_factor == 2

        # Valid: scale_factor only  
        config = ShotConfig({"scale_factor": 1.5})
        assert config.scale_factor == 1.5

        # Invalid: both retina and scale_factor
        with pytest.raises(ValueError, match="retina and --scale-factor cannot be used together"):
            ShotConfig({"retina": True, "scale_factor": 1.5})

        # Invalid: negative scale_factor
        with pytest.raises(ValueError, match="scale-factor must be positive"):
            ShotConfig({"scale_factor": -1})

        # Invalid: zero scale_factor
        with pytest.raises(ValueError, match="scale-factor must be positive"):
            ShotConfig({"scale_factor": 0})

    def test_none_value_filtering(self):
        """Test that None values are filtered correctly"""
        config = ShotConfig({
            "url": "https://example.com",
            "width": None,  # Should be filtered out, use default
            "height": 800,
            "quality": None,  # Should be filtered out
            "javascript": "alert('test')"
        })
        
        assert config.url == "https://example.com"
        assert config.width == 1280  # default, not None
        assert config.height == 800
        assert config.quality is None  # None is allowed after filtering
        assert config.javascript == "alert('test')"

    def test_format_property(self):
        """Test format property based on quality setting"""
        # No quality = PNG
        config = ShotConfig({"url": "test"})
        assert config.format == "png"
        
        # With quality = JPEG
        config = ShotConfig({"url": "test", "quality": 80})
        assert config.format == "jpeg"

    def test_effective_full_page_property(self):
        """Test effective_full_page logic"""
        # No height = full page
        config = ShotConfig({"url": "test"})
        assert config.effective_full_page is True
        
        # With height = not full page, unless selectors
        config = ShotConfig({"url": "test", "height": 600})
        assert config.effective_full_page is False
        
        # With selectors = always full page
        config = ShotConfig({"url": "test", "height": 600, "selectors": ["#test"]})
        assert config.effective_full_page is True

    def test_selector_handling(self):
        """Test selector list processing"""
        config = ShotConfig({
            "url": "test",
            "selectors": ["#one", "#two"],
            "selector": "#single",  # Should be added to list
            "selectors_all": ["div", "span"],
            "js_selectors": ["window.test"]
        })
        
        assert config.selectors == ["#one", "#two", "#single"]
        assert config.selectors_all == ["div", "span"]
        assert config.js_selectors == ["window.test"]
        assert config.has_selectors() is True

    def test_config_file_defaults(self, mocker, tmp_path):
        """Test that config file defaults are loaded"""
        # Mock config directory
        mocker.patch("shot_power_scraper.shot_config.get_config_dir", return_value=tmp_path)
        
        # Create config file
        config_file = tmp_path / "config.json"
        config_file.write_text('{"ad_block": true, "user_agent": "test-agent"}')
        
        config = ShotConfig({"url": "test"})
        assert config.ad_block is True
        assert config.user_agent == "test-agent"
        
        # Command line should override config file
        config = ShotConfig({"url": "test", "ad_block": False})
        assert config.ad_block is False
        assert config.user_agent == "test-agent"  # Still from config file