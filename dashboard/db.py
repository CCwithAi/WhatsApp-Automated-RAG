"""
Shared database helpers for the Dashboard.
"""
import os
import sqlite3
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, date

import pymssql

logger = logging.getLogger("dashboard.db")

INSTANCE = os.environ.get("INSTANCE_NAME", "cleaner")
BRIDGE_DB = os.environ.get("BRIDGE_DB_PATH", "/data/bridge-store/messages.db")
SQL_SERVER = os.environ.get("SQL_SERVER", "host.docker.internal,14314")
SQL_DB = os.environ.get("SQL_DATABASE", "master")
SQL_USER = os.environ.get("SQL_USER", "sa")
SQL_PASS = os.environ.get("SQL_PASSWORD", "")


def get_bridge_conn():
    conn = sqlite3.connect(f"file:{BRIDGE_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def get_sql_conn():
    parts = SQL_SERVER.split(",")
    host = parts[0]
    port = int(parts[1]) if len(parts) > 1 else 1433
    return pymssql.connect(
        server=host, port=port, user=SQL_USER,
        password=SQL_PASS, database=SQL_DB, as_dict=True,
    )


def bridge_query(sql: str, params: tuple = ()) -> List[Dict]:
    conn = get_bridge_conn()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def sql_query(sql: str, params: tuple = ()) -> List[Dict]:
    conn = get_sql_conn()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def sql_execute(sql: str, params: tuple = ()):
    conn = get_sql_conn()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()
    finally:
        conn.close()
