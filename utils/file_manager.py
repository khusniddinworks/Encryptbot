import os
import zipfile
import base64
from typing import Dict
try:
    import pyzipper
except ImportError:
    pyzipper = None

def read_file(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()

def write_file(path: str, data: bytes):
    with open(path, "wb") as f:
        f.write(data)

def delete_file(path: str):
    if os.path.exists(path):
        os.remove(path)

def create_secure_zip(
    zip_path: str,
    encrypted_file_path: str,
    key_data: bytes,
    meta_data: Dict[str, bytes] = None,
    password: str = None
):
    """
    Creates a secure zip.
    If 'password' is provided and pyzipper is available, 
    the ZIP itself will be AES-encoded with that password.
    """
    # Prefer pyzipper for AES encryption if password is provided
    if password and pyzipper:
        with pyzipper.AESZipFile(zip_path, 'w', compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as zf:
            zf.setpassword(password.encode())
            _write_zip_contents(zf, encrypted_file_path, key_data, meta_data)
    else:
        # Fallback to standard zip (no password on zip itself, or legacy if we tried)
        # Note: Standard zipfile supports password but only legacy weak encryption.
        # We stick to no-zip-password if pyzipper missing, trusting our inner encryption.
        with zipfile.ZipFile(zip_path, 'w') as zf:
             # if password: zf.setpassword(password.encode()) # Legacy only, skip for now to avoid confusion
            _write_zip_contents(zf, encrypted_file_path, key_data, meta_data)

import json

def _write_zip_contents(zf, encrypted_file_path, key_data, meta_data):
    zf.write(encrypted_file_path, "data.enc")
    manifest = {
        "key": base64.b64encode(key_data).decode('utf-8') if key_data else None,
        "meta": {}
    }
    if meta_data:
        for name, content in meta_data.items():
            if isinstance(content, bytes):
                manifest["meta"][name] = base64.b64encode(content).decode('utf-8')
            else:
                manifest["meta"][name] = str(content)
    zf.writestr("manifest.json", json.dumps(manifest, indent=2))

def extract_secure_zip(zip_path: str, extract_to: str, password: str = None) -> Dict[str, str]:
    if not pyzipper:
        raise ImportError("pyzipper required")

    try:
        with pyzipper.AESZipFile(zip_path, 'r') as zf:
            if password: zf.setpassword(password.encode())
            zf.extractall(extract_to)
            
            manifest_path = os.path.join(extract_to, "manifest.json")
            if os.path.exists(manifest_path):
                with open(manifest_path, 'r') as f:
                    m = json.load(f)
                    if m.get("key"):
                        with open(os.path.join(extract_to, "key.txt"), 'w') as kf: kf.write(m["key"])
                    for k, v in m.get("meta", {}).items():
                        with open(os.path.join(extract_to, f"{k}.txt"), 'w') as mf: mf.write(v)
            
            return {name: os.path.join(extract_to, name) for name in os.listdir(extract_to)}
    except RuntimeError as e:
        if 'Bad password' in str(e) or 'password required' in str(e):
            raise ValueError("ZIP password incorrect")
        raise e
