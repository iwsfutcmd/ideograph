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
        "Topic :: Text Processing :: Linguistic",
        "Natural Language :: Chinese (Simplified)",
        "Natural Language :: Chinese (Traditional)",
        "Natural Language :: Japanese",
        "Natural Language :: Korean",
        "Natural Language :: Vietnamese",
        "Natural Language :: Zhuang",
    ],
    scripts=["bin/ideograph"],
)