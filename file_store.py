# file_store.py
import os, json, shutil
from config import SERVER_DISK_PATH

CLOUD_ROOT = os.path.join(SERVER_DISK_PATH, "cloud_storage")
os.makedirs(CLOUD_ROOT, exist_ok=True)
INDEX_FILE = os.path.join(CLOUD_ROOT, "index.json")

def _index():
    if not os.path.exists(INDEX_FILE):
        return {}
    try:
        with open(INDEX_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def _save_index(idx):
    with open(INDEX_FILE, "w") as f:
        json.dump(idx, f, indent=2)

def store(file_name: str, size: int, sender: str):
    idx = _index()
    idx[file_name] = {"size": size, "sender": sender}
    _save_index(idx)

def fetch(file_name: str):
    idx = _index()
    return idx.get(file_name)  # returns None if not found

def in_same_link(a: str, b: str) -> bool:
    from links_manager import LinksManager
    lm = LinksManager()
    for nodes in lm.links.values():
        if a in nodes and b in nodes:
            return True
    return False