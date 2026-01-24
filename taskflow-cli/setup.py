from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

with open("requirements.txt") as f:
    requirements = f.read().splitlines()

setup(
    name="taskflow-cli",
    version="2.1.0",
    description="TaskFlow CLI - Distributed Task Orchestrator",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="TaskFlow Team",
    author_email="contact@taskflow.example.com",
    url="https://github.com/yourusername/TaskFlow",
    project_urls={
        "Bug Tracker": "https://github.com/yourusername/TaskFlow/issues",
        "Documentation": "https://taskflow.example.com/docs",
        "Source Code": "https://github.com/yourusername/TaskFlow",
    },
    packages=find_packages(),
    include_package_data=True,
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "taskflow=taskflow.main:run",
        ],
    },
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
        "Environment :: Console",
    ],
    keywords="taskflow cli task orchestrator distributed workflow kubernetes",
)
