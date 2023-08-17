PROJECT_URL = "https://github.com/LibraryOfCongress/bagit-python"


def read_global_docs():
    return """
BagIt is a directory, filename convention for bundling an arbitrary set of
files with a manifest, checksums, and additional metadata. More about BagIt
can be found at:

    http://purl.org/net/bagit

bagit.py is a pure python drop in library and command line tool for creating,
and working with BagIt directories.


Command-Line Usage:

Basic usage is to give bagit.py a directory to bag up:

    $ bagit.py my_directory

This does a bag-in-place operation where the current contents will be moved
into the appropriate BagIt structure and the metadata files will be created.

You can bag multiple directories if you wish:

    $ bagit.py directory1 directory2

Optionally you can provide metadata which will be stored in bag-info.txt:

    $ bagit.py --source-organization "Library of Congress" directory

You can also select which manifest algorithms will be used:

    $ bagit.py --sha1 --md5 --sha256 --sha512 directory


Using BagIt from your Python code:

    import bagit
    bag = bagit.make_bag('example-directory', {'Contact-Name': 'Ed Summers'})
    print(bag.entries)

For more information or to contribute to bagit-python's development, please
visit %(PROJECT_URL)s
    """
