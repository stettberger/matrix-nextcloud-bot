import logging
import os
import re
from nextcloud import NextCloud
import urllib
import tempfile

class Nextcloud:
    def __init__(self, server, user, password):
        self.server = server
        self.user = user
        self.client = NextCloud(endpoint=server, user=user, password=password)

    def upload(self, folder, name, local_fn=None, url=None):
        res = self.client.list_folders(self.user, path=folder)
        if not res.is_ok:
            return False, f"error accessing folder: {folder} {res}"
        listing = res.data

        if url:
            tmpfile = tempfile.NamedTemporaryFile()
            urllib.request.urlretrieve(url, tmpfile.name)
            local_fn = tmpfile.name

        file_size = os.stat(local_fn).st_size
        filenames = {urllib.parse.unquote(os.path.basename(entry['href'])): entry for entry in listing[1:]}
        if name in filenames:
            if os.stat(local_fn).st_size == int(filenames[name]['content_length']):
                return True, f"file already present: {name}"

        # Choose new name, if the old one is already
        i = 1
        base, ext = os.path.splitext(name)
        while name in filenames:
            name = f"{base} ({i}){ext}"
            i += 1

        target = os.path.join(folder, name)
        res =  self.client.upload_file(self.user, local_fn, target)
        if not res.is_ok:
            return False, f"error uploading file: {target} {res}"

        mbytes = file_size / 1024./1024.
        return True, f"file upload ok: {folder}{name} ({mbytes:.2f}mB)"
        
