from copy import copy, deepcopy
from hashlib import sha256
import hashlib
from mimetypes import read_mime_types
import shutil
import sys
import os
from typing import Any, List
import json
import urllib.parse
from requests import request
import requests
import yaml
import humanize

blacklist = {}

blacklist_pkg = ["android-ndk", "archicad-apidevkit", "qt", "zulu-openjdk", "physx",
                 "openjdk", "cern-root", "geotrans", "strawberryperl", "imagl", "wtl",
                 "openvr", "ogre", "bullet3", "ktx", "osgearth", "libnova", "mpir",
                 "angelscript", "voropp", "co", "eabase", "ignition-tools", "sophus",
                 "stx", "troldal-zippy"]

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

    def remove(self, item: Item):
        if item.sha256 in self._manifest["files"]:
            self._manifest["files"].pop(item.sha256)

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

    def convert_url_to_list(self):
        for sha256 in self._manifest["files"]:
            url = self._manifest["files"][sha256]["url"]
            if not isinstance(url, (list, tuple)):
                url = [url]
                self._manifest["files"][sha256]["url"] = url

    def sha256_to_lower(self):
        new_manifest = deepcopy(self._manifest)
        for sha256 in self._manifest["files"]:
            sha256_l = sha256.lower()
            if sha256 != sha256_l:
                print(f"Convert {sha256} to {sha256_l}")
                item = new_manifest["files"].pop(sha256)
                new_manifest["files"][sha256_l] = item
        self._manifest = new_manifest

def is_blacklist_pkg(filename) -> bool:
    for p in blacklist_pkg:
        if f"recipes/{p}/" in filename:
            return True
    return False

def parse_from_cci(cci: str, need_blacklist = False) -> List[Item]:
    items = list()
    conandatas = list()
    for dirpath, dirnames, filenames in os.walk(os.path.join(cci, "recipes")):
        for filename in filenames:
            #print(f"{dirpath} {dirnames} {filenames}")
            if filename.endswith("conandata.yml"):
                f = os.path.join(dirpath, filename)

                if need_blacklist:
                    if is_blacklist_pkg(f):
                        print(f"Add blacklist file {f}")
                        conandatas.append(f)
                else:
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
            items.append(Item(obj["sha256"].lower(), url_parsed))
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

def hash_from_path(filename: str):
    hash = filename[-65:]
    hash = hash.replace("/", "")
    return hash

def hash_to_path(sha256: str):
    return os.path.join(sha256[0:2], sha256[2:])

def hash_sha256(path: str) -> str:
    with open(path, "rb") as f:
        data = f.read()
        return hashlib.sha256(data).hexdigest().lower()

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

def cmd_convert_to_list(cci: str, dst: str):
    manifest = read_manifest(dst)
    manifest.backup()
    manifest.convert_url_to_list()
    manifest.flush()

class DistFile:
    def __init__(self, path, stat) -> None:
        self.path = path
        self.stat = stat
        pass

def cmd_sort_files(cci: str, dst: str):
    files = list()
    manifest = read_manifest(dst)
    for dirpath, dirnames, filenames in os.walk(os.path.join(dst, "files")):
        for filename in filenames:
            f = os.path.join(dirpath, filename)
            stat = os.stat(f)
            files.append(DistFile(f, stat))
    files.sort(key=lambda f: f.stat.st_size)
    for file in files:
        size = humanize.naturalsize(file.stat.st_size, binary=True)
        sha256 = hash_from_path(file.path)
        try:
            url = manifest._manifest["files"][sha256]["url"]
        except:
            url = "Unknown"
        print(f"{size}\t{file.path}\t{url}")

def cmd_to_lower(cci: str, dst: str):
    manifest = read_manifest(dst)
    manifest.backup()
    manifest.sha256_to_lower()
    manifest.flush()

def cmd_filename_to_lower(cci: str, dst: str):
    for dirpath, dirnames, filenames in os.walk(os.path.join(dst, "files")):
        for filename in filenames:
            f = os.path.join(dirpath, filename)
            f_l = f.lower()
            if f != f_l:
                print(f"Move {f} to {f_l}")
                shutil.move(f, f_l)

def cmd_clean_for_blacklist(cci: str, dst: str):
    items = parse_from_cci(cci, need_blacklist=True)
    manifest = read_manifest(dst)
    manifest.backup()
    for item in items:
        file = os.path.join(dst, "files", hash_to_path(item.sha256))
        if os.path.exists(file):
            print(f"Remove {file}")
            os.remove(file)
        manifest.remove(item)
    manifest.flush()

def cmd_check_consistency(cci: str, dst: str):
    manifest = read_manifest(dst)
    manifest.backup()
    manifest_ori = deepcopy(manifest._manifest)
    for sha256 in manifest_ori["files"]:
        file = os.path.join(dst, "files", hash_to_path(sha256))
        if not os.path.exists(file):
            print(f"File for {sha256} not exist {file}")
            manifest._manifest["files"].pop(sha256)
        else:
            # Check sum
            size = os.stat(file).st_size
            if size <= 10 * 1024 * 1024 and hash_sha256(file) != sha256:
                print(f"Hash mismatch for file {file}, remove it")
                os.remove(file)   
                manifest._manifest["files"].pop(sha256)
    manifest.flush()

def cmd_garbage_collection(cci: str, dst: str):
    files = list()
    manifest = read_manifest(dst)
    for dirpath, dirnames, filenames in os.walk(os.path.join(dst, "files")):
        for filename in filenames:
            f = os.path.join(dirpath, filename)
            files.append(f)
    for file in files:
        sha256 = hash_from_path(file)
        if sha256 not in manifest._manifest["files"]:
            print(f"Garbage file {file}, remove it")
            os.remove(file)

if sys.argv[1] == "download_from_cci":
    cmd_download_from_cci(sys.argv[2], sys.argv[3])
elif sys.argv[1] == "convert_to_list":
    cmd_convert_to_list(sys.argv[2], sys.argv[3])
elif sys.argv[1] == "to_lower":
    cmd_to_lower(sys.argv[2], sys.argv[3])
elif sys.argv[1] == "filename_to_lower":
    cmd_filename_to_lower(sys.argv[2], sys.argv[3])
elif sys.argv[1] == "sort_files":
    cmd_sort_files(sys.argv[2], sys.argv[3])
elif sys.argv[1] == "clean_for_blacklist":
    cmd_clean_for_blacklist(sys.argv[2], sys.argv[3])
elif sys.argv[1] == "check_consistency":
    cmd_check_consistency(sys.argv[2], sys.argv[3])
elif sys.argv[1] == "garbage_collection":
    cmd_garbage_collection(sys.argv[2], sys.argv[3])
else:
    raise Exception(f"Unknown command {sys.argv[1]}")
