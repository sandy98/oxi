from setuptools import setup, find_packages
from oxi import (__version__, __author__, __email__, __license__, 
                 __url__, __description__, __copyright__)

setup(
    name='oxi',
    version=__version__,
    description=__description__,
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author=__author__,
    author_email=__email__,
    url=__url__,
    packages=find_packages(),
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.9',
    entry_points={
        'console_scripts': [
            'mp4parser=oxi.mp4parser:main',
        ],
    },
    license='MIT',
    license_files=('LICENSE',),    
)