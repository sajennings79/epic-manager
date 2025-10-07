#!/usr/bin/env python3
"""
Setup script for Epic Manager

This file provides backward compatibility and additional setup functionality
beyond what pyproject.toml can provide.
"""

from setuptools import setup, find_packages

setup(
    name="epic-manager",
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'epic-mgr=epic_manager.cli:main',
        ],
    },
    include_package_data=True,
    zip_safe=False,
    python_requires='>=3.11',
)