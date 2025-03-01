import sqlite3
import os
import hashlib


def get_games(database_path):
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()
    cursor.execute("SELECT ZNAME, ZIdentifier FROM zgame")
    games = cursor.fetchall()
    conn.close()
    return games


