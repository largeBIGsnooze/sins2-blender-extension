import zipfile, os, shutil, json
from datetime import datetime

try:
    from urllib.request import Request, urlopen
except ImportError:
    from urllib2 import urlopen, Request, URLError


class Github:
    def __init__(self, dist):
        self.dist = dist
        self.author = "largeBIGsnooze"
        self.repo = "sins2-blender-extension"
        self.api = f"https://api.github.com/repos/{self.author}/{self.repo}"
        self.temp = os.path.join(self.dist, "sins2_extension-temp")

    def fetch_latest_commit(self):
        url = f"{self.api}/commits"
        try:
            response = urlopen(url)
            if response.getcode() == 200:
                first_commit = json.loads(response.read())[0]["sha"]
                return first_commit
        except Exception as e:
            print(f"Github.fetch_commits() failed Github API request: {e}")

    def fetch_latest_archive(self):
        zip_file = os.path.join(self.dist, "master.zip")
        url = f"{self.api}/zipball"
        try:
            response = urlopen(url)
            os.makedirs(self.temp, exist_ok=True)
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
