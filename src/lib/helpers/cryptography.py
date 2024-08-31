import hashlib, os


def generate_hash_from_directory(directory):
    hash = hashlib.sha256()
    for dirpath, dirname, filenames in os.walk(directory):
        if ".git" in dirpath:
            continue
        for filename in filenames:
            if "pyc" in filename:
                continue
            with open(os.path.join(dirpath, filename), "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hash.update(chunk)

    return hash.hexdigest()
