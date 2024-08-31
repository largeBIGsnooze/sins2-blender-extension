import zipfile, os, shutil
from datetime import datetime
from .helpers.cryptography import generate_hash_from_directory

try:
    from urllib.request import Request, urlopen
except ImportError:
    from urllib2 import urlopen, Request, URLError


class Github_Downloader:
    def __init__(self, dist):
        self.url = "https://github.com"
        self.author = "largeBIGsnooze"
        self.repo = "sins2-blender-extension"
        self.zipball = "archive/refs/heads/master.zip"
        self.dist = dist
        self.temp = os.path.join(self.dist, "temp")

    @staticmethod
    def initialize(dist):
        g = Github_Downloader(dist)
        zip_file = os.path.join(g.temp, "master.zip")
        g.fetch_latest_archive(zip_file)

    def fetch_latest_archive(self, zip_file):
        url = f"{self.url}/{self.author}/{self.repo}/{self.zipball}"
        response = urlopen(url)
        os.makedirs(self.temp, exist_ok=True)
        try:
            if response.getcode() == 200:
                with open(zip_file, "wb") as f:
                    f.write(response.read())
                self.extract(zip_file)
        except Exception as e:
            print(f"Github.fetch_latest_archive() failed archive request: {e}")

    def extract(self, zip_file):
        with zipfile.ZipFile(zip_file, "r") as z:
            for file_info in z.infolist():
                file_path = file_info.filename
                extract_path = os.path.join(self.temp, file_path.split("/", 1)[1])
                if file_info.is_dir():
                    os.makedirs(extract_path, exist_ok=True)
                    continue
                shutil.copyfileobj(z.open(file_info), open(extract_path, "wb"))
        os.remove(zip_file)
