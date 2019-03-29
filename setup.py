import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="ideograph",
    version="1.0.0",
    author="Ben Yang",
    author_email="benayang@gmail.com",
    description="Tool for finding ideographic (e.g. Han) characters from their components",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/iwsfutcmd/ideograph",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    scripts=["bin/ideograph"],
)