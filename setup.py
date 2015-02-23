"""Set up for xblock-utils"""
import os
import os.path
from setuptools import setup

def package_data(pkg, root_list):
    """Generic function to find package_data for `pkg` under `root`."""
    data = []
    for root in root_list:
        for dirname, _, files in os.walk(os.path.join(pkg, root)):
            for fname in files:
                data.append(os.path.relpath(os.path.join(dirname, fname), pkg))

    return {pkg: data}

setup(
    name='xblock-utils',
    version='0.1a0',
    description='Various utilities for XBlocks',
    packages=['xblockutils'],
    install_requires=['XBlock'],
	package_data=package_data("xblockutils", ["public", "templates"]),
)