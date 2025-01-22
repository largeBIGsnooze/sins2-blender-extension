import os


def normalize(file_path, args):
    return os.path.normpath(os.path.join(file_path, args))


def rename(path, dest, filename):
    os.replace(os.path.join(path, filename), os.path.join(dest, filename))


def basename(filename):
    return os.path.basename(os.path.splitext(filename)[0])
