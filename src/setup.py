#!/usr/bin/env python3

import os

from setuptools import setup, find_packages


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def read_list(file_path):
    if not os.path.isfile(file_path):
        return []
    ret_list = []
    with open(file_path, "r", encoding="utf-8") as content_file:
        for line in content_file:
            ret_list.append(line.strip())
    return ret_list


packages_list = find_packages(include=["cppincludegraph", "cppincludegraph.*"])

packages_data = {"cppincludegraph": ["template/*.tmpl"]}

## additional scripts to install
additional_scripts = ["cppincludegraphdump", "cppincludegraphgen"]

## every time setup info changes then version number should be increased

setup(
    name="cppincludegraph",
    version="2.0.2",
    description="headers include graph generator for C++ projects",
    url="https://github.com/anetczuk/cpp-include-graph",
    author="anetczuk",
    license="BSD 3-Clause",
    packages=packages_list,
    package_data=packages_data,
    scripts=additional_scripts,
    install_requires=["texthon", "showgraph @ git+https://github.com/anetczuk/showgraph-py#subdirectory=src"],
)
