from setuptools import setup, find_packages

setup(
    name="terroir",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "anthropic>=0.8.0",
        "langchain>=0.1.0",
        "chromadb>=0.4.0",
        "beautifulsoup4",
        "requests",
        "selenium",
        "webdriver_manager"
    ]
) 