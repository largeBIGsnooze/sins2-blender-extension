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
        self.hash = None
        self.body = ""

    def request(self, url):
        response = urlopen(url)
        try:
            if response.getcode() == 200:
                response = response.read()
            return response
        except Exception as e:
            print(f"Github.request() failed request: {e}")
        return None

    def fetch_latest_downloadable_release_data(self):
        url = f"{self.api}/releases"
        response = json.loads(self.request(url).decode("utf-8"))[0]
        assets = response["assets"][0]
        self.body = response["body"]
        self.hash = assets["digest"].split("sha256:")[1]
        return assets["browser_download_url"]

    def fetch_latest_archive(self):
        zip_file = os.path.join(self.dist, "master.zip")
        os.makedirs(self.temp, exist_ok=True)
        release = self.request(self.fetch_latest_downloadable_release_data())

        with open(zip_file, "wb") as f:
            f.write(release)
        self.extract(zip_file)

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
