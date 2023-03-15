import shutil
import sys
import os
from typing import Any, List, Optional
import json
import urllib.request
import urllib.parse
from requests import request
import requests
import yaml

blacklist = {
    "9dcfba4c2efa8d44bf4cc9edd324794865dd6d6331467d3c69f5c5574db3844e": "https://gitlab-lepuy.iut-clermont.uca.fr/opengl/imagl/-/archive/v0.1.0/imagl-v0.1.0.tar.gz",
    "4a7502cc733431af6423246fe5144e2eddb984454a66cca51742c852980ac862": "https://gitlab-lepuy.iut-clermont.uca.fr/opengl/imagl/-/archive/v0.1.1/imagl-v0.1.1.tar.gz",
    "d1edf74e00f969a47dc56e4400b805600d6997270339d49e91b7c6112a2cb37e": "https://gitlab-lepuy.iut-clermont.uca.fr/opengl/imagl/-/archive/v0.1.2/imagl-v0.1.2.tar.gz",
    "5a68cdeff4338e411695cca16c4230567de298f8efee2a9fadcc6fa644a70248": "https://gitlab-lepuy.iut-clermont.uca.fr/opengl/imagl/-/archive/v0.2.1/imagl-v0.2.1.tar.gz",
    "c03f80c66f28e86b3cc7c98d14afab6bec8eb9366476f6bdda8469c35f52b18a": "https://iweb.dl.sourceforge.net/project/wtl/WTL%209.1/WTL%209.1.5321%20Final/WTL91_5321_Final.zip",
    "b9fff11c36532c5fa0114b3c7ee4f752cbef71c7ddfd2e5f88f6f51f15431104": "https://iweb.dl.sourceforge.net/project/wtl/WTL%2010/WTL%2010.0.9163/WTL10_9163.zip",
}

blacklist_pkg = ["android-ndk", "archicad-apidevkit"]

class Item:
    def __init__(self, sha256: str, url: List[str]) -> None:
        self.sha256 = sha256
        self.url = url

class Manifest:
    def __init__(self) -> None:
        pass

    def append(self, item: Item):
        print(f"Add item {item.url} {item.sha256}")
        self._manifest["files"][item.sha256] = { "url": item.url }

    def flush(self):
        file = open(self._path, "w")
        json_str = json.dump(self._manifest, file, indent=2)

    def filter(self, items: List[Item]) -> List[Item]:
        new_items = list()
        for item in items:
            if item.sha256 not in self._manifest["files"] and \
               item.sha256 not in blacklist:
                new_items.append(item)
        return new_items
    def backup(self):
        i = 0
        while os.path.exists(f"{self._path}.{i}"):
            i += 1
        shutil.copy2(self._path, f"{self._path}.{i}")

def is_blacklist_pkg(filename) -> bool:
    for p in blacklist_pkg:
        if f"recipes/{p}" in filename:
            return True
    return False

def parse_from_cci(cci: str) -> List[Item]:
    items = list()
    conandatas = list()
    for dirpath, dirnames, filenames in os.walk(os.path.join(cci, "recipes")):
        for filename in filenames:
            #print(f"{dirpath} {dirnames} {filenames}")
            if filename.endswith("conandata.yml"):
                f = os.path.join(dirpath, filename)
                if is_blacklist_pkg(f):
                    print(f"Skip file {f}")
                else:
                    conandatas.append(f)
    for conandata in conandatas:
        items.extend(parse_from_conandata(conandata))
    return items

def try_extract(obj: Any) -> List[Item]:
    items = list()
    if isinstance(obj, dict):
        if "url" in obj and "sha256" in obj:
            if not isinstance(obj["url"], (list, tuple)):
                url = [obj["url"]]
            else:
                url = obj["url"]
            url_parsed = list()
            for i in url:
                url_parsed.append(("%20").join(i.split(" ")))
            items.append(Item(obj["sha256"], url_parsed))
        else:
            for k in obj:
                items.extend(try_extract(obj[k]))
    elif isinstance(obj, (list, tuple)):
        for i in obj:
            items.extend(try_extract(i))
    return items

def parse_from_conandata(conandata: str) -> List[Item]:
    items = list()
    conandata_obj = yaml.full_load(open(conandata, "r"))
    for version in conandata_obj["sources"]:
        # print(conandata_obj["sources"][version])
        """
        if "url" not in conandata_obj["sources"][version] or \
           "sha256" not in conandata_obj["sources"][version]:
            extract = try_extract(conandata_obj["sources"][version])
            print("Skip {}".format(conandata_obj["sources"][version]))
            continue
        url = conandata_obj["sources"][version]["url"]
        if not isinstance(url, (tuple, list)):
            url = [url]
        # url = urllib.parse.quote_plus(url)
        # url = ('+').join(url.split(' '))
        url_parsed = list()
        for i in url:
            url_parsed.append(("%20").join(i.split(" ")))
        sha256 = conandata_obj["sources"][version]["sha256"]
        items.append(Item(sha256, url_parsed))
        """
        extract = try_extract(conandata_obj["sources"][version])
        if len(extract) == 0:
            print("Skip {}".format(conandata_obj["sources"][version]))
        else:
            items.extend(extract)
    return items

def read_manifest(dst: str) -> Manifest:
    manifest_path = os.path.join(dst, "manifest.json")
    if not os.path.exists(manifest_path):
        init = r'{"files": {}}'
        f = open(manifest_path, "w")
        f.write(init)
        f.close()
    manifest_file = open(manifest_path, "r")
    manifest_json = json.load(manifest_file)
    manifest = Manifest()
    manifest._manifest = manifest_json
    manifest._path = manifest_path
    return manifest

def download_to(dst: str, url: str, sha256: str) -> bool:
    dst_filename = os.path.join(dst, "files", sha256[0:2], sha256[2:])
    os.makedirs(os.path.join(dst, "files", sha256[0:2]), exist_ok=True)
    print(f"Downloading {url} to {dst_filename} ...")
    left = 2
    while left > 0:
        try:
            # urllib.request.urlretrieve(url, dst_filename)
            # opener = urllib.request.URLopener()
            # opener.addheader("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/109.0")
            # opener.retrieve(url, dst_filename)
            # opener.close()
            r = requests.get(url)
            with open(dst_filename, "wb") as out:
                out.write(r.content)
            break
        except Exception as e:
            print(f"Download failed {left}: {e}")
            left -= 1
    if left == 0:
        return False
    else:
        return True

# Commands

def cmd_download_from_cci(cci: str, dst: str):
    items = parse_from_cci(cci)
    manifest = read_manifest(dst)
    items = manifest.filter(items)

    for item in items:
        for i in item.url:
            if download_to(dst, i, item.sha256):
                manifest.append(item)
                manifest.flush()
                break

if sys.argv[1] == "download_from_cci":
    cmd_download_from_cci(sys.argv[2], sys.argv[3])
