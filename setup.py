from setuptools import setup, find_packages

setup(
    name='aiogram-callback-manager',
    version='0.1.2',
    author='EvilMathHippy',
    author_email='careviolan@gmail.com',
    description='Асинхронный менеджер callback для aiogram.',
    long_description=open('README.md', encoding='utf-8').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/megamen932/aiogram-callback-manager',
    packages=find_packages(),
    install_requires=[
        'aiogram>=3.0.0b5',
        'aiosqlite>=0.17.0',
    ],
    classifiers=[
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.7',
)
