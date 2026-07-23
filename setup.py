"""Packaging configuration for the options-platform library."""

from pathlib import Path

from setuptools import find_packages, setup

ROOT = Path(__file__).parent
LONG_DESCRIPTION = (ROOT / "README.md").read_text(encoding="utf-8")


setup(
    name="options-platform",
    version="0.1.0",
    description="Modular quantitative options pricing and paper-trading platform.",
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    author="Anup Mayank",
    python_requires=">=3.11",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    include_package_data=True,
    install_requires=[
        "numpy>=1.26",
        "scipy>=1.11",
        "pandas>=2.1",
        "streamlit>=1.30",
        "plotly>=5.18",
        "yfinance>=0.2.40",
        "SQLAlchemy>=2.0",
        "pydantic>=2.5",
        "python-dateutil>=2.9",
        "PyYAML>=6.0",
        "loguru>=0.7",
    ],
    extras_require={
        "dev": [
            "pytest>=8.0",
            "pytest-cov>=4.1",
            "ruff>=0.4",
            "mypy>=1.8",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Office/Business :: Financial :: Investment",
    ],
)
