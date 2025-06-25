from setuptools import setup, find_packages

setup(
    name="tinyllama",
    version="0.1.0",
    package_dir={"": "01_src"},
    packages=find_packages(where="01_src"),
    install_requires=[
        "cryptography",
        "python-jose",
        "fastapi",
        "httpx",
        "pydantic-settings",
        "python-dotenv",
    ],

)
