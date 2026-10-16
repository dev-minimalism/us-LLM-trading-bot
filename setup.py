"""
Setup configuration for AI Trading Bot package
"""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="ai-trading-bot",
    version="2.0.0",
    author="Yungoo Park",
    description="AI-powered automated trading system for US stocks using Gemini AI and Alpaca broker",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/dev-minimalism/us-LLM-trading-bot",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Financial and Insurance Industry",
        "Topic :: Office/Business :: Financial :: Investment",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        'console_scripts': [
            'trading-bot-v1-basic=src.systems.v1.basic_ai:main',
            'trading-bot-v2-event=src.systems.v2.event_driven:main',
            'trading-bot-v2-hybrid=src.systems.v2.hybrid:main',
        ],
    },
    include_package_data=True,
    package_data={
        '': ['*.md', '*.txt'],
    },
)