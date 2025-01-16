from setuptools import find_packages, setup

setup(
    name="sparkhouse",
    version="0.1.0",
    packages=find_packages(exclude=["tests"]),
    python_requires=">=3.9",
    install_requires=["pyspark>=3.5,<3.6"],
)
