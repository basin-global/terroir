from setuptools import setup, find_packages

setup(
    name="terroir",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.109.0",
        "uvicorn>=0.27.0",
        "python-dotenv>=1.0.0",
        "asyncpg>=0.29.0",
        "anthropic>=0.17.0",
        "langchain>=0.1.0",
        "langchain-anthropic>=0.1.1",
        "pydantic>=2.6.0",
        "pydantic-settings>=2.1.0",
        "watchdog>=3.0.0",
        "web3>=6.0.0,<7.0.0"
    ],
    python_requires=">=3.9",
) 