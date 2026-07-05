from setuptools import find_packages, setup


setup(
    name="tripp-mind-sdk",
    version="0.1.0",
    description="Python SDK for the Tripp.Mind knowledge management API gateway.",
    packages=find_packages(include=["tripp_mind_sdk", "tripp_mind_sdk.*"]),
    package_data={"tripp_mind_sdk": ["py.typed"]},
    python_requires=">=3.9",
    install_requires=["requests>=2.28.0"],
    extras_require={"test": ["pytest>=7.0.0"]},
)
