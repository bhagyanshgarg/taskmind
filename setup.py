from setuptools import setup, find_packages

setup(
    name="taskmind",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "PyYAML>=5.1",
        "click>=7.0",
        "pystray>=0.19",
        "Pillow>=6.0",
        "apscheduler>=3.6",
    ],
    entry_points={
        "console_scripts": [
            "taskmind=taskmind.cli:main",
        ],
    },
    python_requires=">=3.6",
)
