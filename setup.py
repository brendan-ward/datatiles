import os
from setuptools import setup

setup(
    name='datatiles',
    version='0.1.0',
    packages=['datatiles'],
    url='https://github.com/brendan-ward/datatiles',
    license='MIT',
    author='Brendan C. Ward',
    author_email='bcward@consbio.org',
    description='Convert raster data to tiles',
    long_description_content_type='text/markdown',
    long_description=open('README.md').read(),
    install_requires=['rasterio>=1.0', 'Pillow', 'numpy', 'mercantile', 'pymbtiles', 'click', 'progress'],
    include_package_data=True,
    extras_require={
        'test': ['pytest', 'pytest-cov'],
    }
)
