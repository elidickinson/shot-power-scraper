import os
from setuptools import setup

VERSION = "1.8"


def get_long_description():
    with open(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "README.md"),
        encoding="utf8",
    ) as fp:
        return fp.read()


setup(
    name="shot-power-scraper",
    description="A powerful command-line utility for taking automated screenshots of websites with enhanced capabilities",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    author="Simon Willison",
    url="https://github.com/user/shot-power-scraper",
    project_urls={
        "Issues": "https://github.com/user/shot-power-scraper/issues",
        "CI": "https://github.com/user/shot-power-scraper/actions",
        "Changelog": "https://github.com/user/shot-power-scraper/releases",
    },
    license="Apache License, Version 2.0",
    version=VERSION,
    packages=["shot_power_scraper"],
    entry_points="""
        [console_scripts]
        shot-power-scraper=shot_power_scraper.cli:cli
    """,
    install_requires=["click", "PyYAML", "nodriver", "click-default-group"],
    extras_require={"test": ["pytest", "cogapp", "pytest-mock"]},
    python_requires=">=3.7",
)
