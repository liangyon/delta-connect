import sqlite3
import os
import hashlib

def get_games(database_path):
    conn = sqlite3.connect("./Delta.sqlite")
    cursor = conn.cursor()
    cursor.execute("SELECT ZNAME, ZIdentifier FROM zgame")
    games = cursor.fetchall()
    conn.close()
    return games


def get_file_hash(file_path):
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def sync_files(local_file, remote_file):
    if get_file_hash(local_file) != get_file_hash(remote_file):
        # Perform sync logic here
        pass