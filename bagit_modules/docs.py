PROJECT_URL = "https://github.com/LibraryOfCongress/bagit-python"


def read_global_docs():
    with open("docstring.txt", "r") as f:
        return f.read() % globals()
