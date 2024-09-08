import hashlib, os


def generate_hash_from_directory(directory, file_list):
    hash = hashlib.sha256()
    for file in file_list:
        if not os.path.isdir(os.path.join(directory, file)):
            with open(os.path.join(directory, file), "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hash.update(chunk)

    return hash.hexdigest()
