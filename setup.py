#!/usr/bin/env python

import sys
from setuptools import setup

if sys.version_info < (2, 7):
    raise NotImplementedError("Sorry, Python 2.X isn't supported.")

import hakase

setup(name='hakase',
    version=hakase.__version__,
    description='Python type serialization library intended for lightweight storage and communication with other processes.',
    long_description=hakase.__doc__,
    long_description_content_type="text/markdown",
    author=hakase.__author__,
    author_email='naphtha@lotte.link',
    url='https://github.com/naphthasl/hakase',
    py_modules=['hakase'],
    license=hakase.__license__,
    install_requires=[
        'xxhash',
        'brotli'
    ],
    platforms='any',
    classifiers=[
            'Operating System :: OS Independent',
            'Intended Audience :: Developers',
            'License :: OSI Approved :: MIT License',
            'Programming Language :: Python :: 3',
            'Programming Language :: Python :: 3.4',
            'Programming Language :: Python :: 3.5',
            'Programming Language :: Python :: 3.6',
            'Programming Language :: Python :: 3.7',
            'Programming Language :: Python :: 3.8',
        ],
    )
