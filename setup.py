#!/usr/bin/env python3

from setuptools import setup, find_packages


setup(
    name="stiefelsystem",
    version="0.1",
    description="Boot your operating system on a different hardware device via network",
    long_description=(
        "When you have more powerful hardware at hand than e.g. your laptop, "
        "and you don't want to maintain two operating systems, this tool "
        "may be for you: With the Stiefelsystem, you can start your "
        "computer's operating system on another hardware over a simple "
        "network link. A link with 1 gbit is sufficient for nearly all use-cases!"
    ),
    maintainer="SFT Technologies",
    maintainer_email="jj@sft.lol",
    url="https://github.com/SFTtech/stiefelsystem",
    project_urls={
        "Bug Tracker": "https://github.com/SFTtech/stiefelsystem/issues",
    },
    license='GPL3+',
    python_requires='>=3.9',
    packages=find_packages(),
    package_data={
        "stiefelsystem": ["etc/*"],
        "stiefelsystem.platform": ["files/**/*"],
    },
    platforms=[
        'Linux',
    ],
    install_requires=[
        'pyyaml',
        'aiohttp',
        'pycryptodome',
    ],
    classifiers=[
        ("License :: OSI Approved :: "
         "GNU General Public License v3 or later (GPLv3+)"),
        "Environment :: Console",
        "Operating System :: POSIX :: Linux"
    ],
    entry_points={
        'console_scripts': [
            'stiefelctl=stiefelsystem.main:main',
        ]
    },
)
