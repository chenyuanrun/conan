import json
import os

def pre_download(conanfile, url, filename, md5=None, sha1=None, sha256=None):
    if sha256 == None:
        return
    cache_path = conanfile._conan_helpers.cache.cache_folder
    config_path = os.path.join(cache_path, "download_mirror.json")
    try:
        with open(config_path, "rb") as f:
            config = json.load(f)
    except:
        return
    mirror_base = config["base"]
    file_mirror = f"{mirror_base}/files/{sha256[:2]}/{sha256[2:]}"
    url.insert(0, file_mirror)
