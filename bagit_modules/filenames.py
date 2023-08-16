def encode_filename_chain(s):
    return s.replace("\r", "%0D").replace("\n", "%0A")


def decode_filename_replace(s):
    return s.replace("%0D", "\r").replace("%0A", "\n").replace("%0d", "\r").replace("%0a", "\n")
