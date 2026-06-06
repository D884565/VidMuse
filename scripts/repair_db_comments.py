"""Repair MySQL table and column comments from resources/init.sql."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pymysql


ROOT = Path(__file__).resolve().parents[1]
INIT_SQL_PATH = ROOT / "resources" / "init.sql"
DEFAULT_DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "aigc_user",
    "password": "123456",
    "database": "aigc_video",
    "charset": "utf8mb4",
    "autocommit": False,
}

TABLE_BLOCK_RE = re.compile(
    r"CREATE TABLE IF NOT EXISTS\s+`?([a-zA-Z0-9_]+)`?\s*\((.*?)\)\s*ENGINE=.*?COMMENT='((?:[^'\\]|\\.)*)';",
    re.S,
)
COLUMN_LINE_RE = re.compile(r"^\s*`?([a-zA-Z0-9_]+)`?\s+")
COMMENT_RE = re.compile(r"\s+COMMENT\s+'((?:[^'\\]|\\.)*)'")
SHOW_CREATE_TABLE_RE = re.compile(r"CREATE TABLE\s+`[^`]+`\s*\((.*)\)\s*ENGINE=", re.S)
SHOW_TABLE_COMMENT_RE = re.compile(r"\)\s*ENGINE=.*?\sCOMMENT='((?:[^'\\]|\\.)*)'", re.S)


def unescape_sql_string(value: str) -> str:
    return value.replace("\\'", "'").replace("\\\\", "\\")


def escape_sql_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "''")


def parse_init_sql_comments(sql_text: str) -> dict[str, dict[str, object]]:
    comments: dict[str, dict[str, object]] = {}
    for table_name, body, table_comment in TABLE_BLOCK_RE.findall(sql_text):
        column_comments: dict[str, str] = {}
        for raw_line in body.splitlines():
            line = raw_line.strip().rstrip(",")
            if not line:
                continue
            upper = line.upper()
            if upper.startswith(("PRIMARY KEY", "FOREIGN KEY", "UNIQUE KEY", "KEY ", "INDEX ", "FULLTEXT ")):
                continue

            column_match = COLUMN_LINE_RE.match(line)
            comment_match = COMMENT_RE.search(line)
            if column_match and comment_match:
                column_comments[column_match.group(1)] = unescape_sql_string(comment_match.group(1))

        comments[table_name] = {
            "table_comment": unescape_sql_string(table_comment),
            "columns": column_comments,
        }

    return comments


def extract_column_definitions(show_create_table: str) -> dict[str, str]:
    body_match = SHOW_CREATE_TABLE_RE.search(show_create_table)
    if body_match is None:
        raise ValueError("Unable to parse SHOW CREATE TABLE output")

    definitions: dict[str, str] = {}
    for raw_line in body_match.group(1).splitlines():
        line = raw_line.strip().rstrip(",")
        if not line.startswith("`"):
            continue

        column_match = COLUMN_LINE_RE.match(line)
        if column_match is None:
            continue

        column_name = column_match.group(1)
        definition = COMMENT_RE.sub("", line).strip()
        definitions[column_name] = definition

    return definitions


def extract_column_comments(show_create_table: str) -> dict[str, str]:
    body_match = SHOW_CREATE_TABLE_RE.search(show_create_table)
    if body_match is None:
        raise ValueError("Unable to parse SHOW CREATE TABLE output")

    comments: dict[str, str] = {}
    for raw_line in body_match.group(1).splitlines():
        line = raw_line.strip().rstrip(",")
        if not line.startswith("`"):
            continue

        column_match = COLUMN_LINE_RE.match(line)
        if column_match is None:
            continue

        comment_match = COMMENT_RE.search(line)
        comments[column_match.group(1)] = unescape_sql_string(comment_match.group(1)) if comment_match else ""

    return comments


def extract_table_comment(show_create_table: str) -> str:
    match = SHOW_TABLE_COMMENT_RE.search(show_create_table)
    if match is None:
        return ""
    return unescape_sql_string(match.group(1))


def build_comment_fix_sql(table_name: str, show_create_table: str, desired: dict[str, object]) -> list[str]:
    statements: list[str] = []
    column_definitions = extract_column_definitions(show_create_table)
    current_column_comments = extract_column_comments(show_create_table)
    desired_columns: dict[str, str] = desired.get("columns", {})  # type: ignore[assignment]

    for column_name, comment in desired_columns.items():
        definition = column_definitions.get(column_name)
        if definition is None:
            continue
        if current_column_comments.get(column_name, "") == comment:
            continue
        escaped_comment = escape_sql_string(comment)
        statements.append(
            f"ALTER TABLE `{table_name}` MODIFY COLUMN {definition} COMMENT '{escaped_comment}';"
        )

    desired_table_comment = str(desired.get("table_comment", ""))
    if desired_table_comment and extract_table_comment(show_create_table) != desired_table_comment:
        statements.append(
            f"ALTER TABLE `{table_name}` COMMENT = '{escape_sql_string(desired_table_comment)}';"
        )

    return statements


def load_desired_comments() -> dict[str, dict[str, object]]:
    return parse_init_sql_comments(INIT_SQL_PATH.read_text(encoding="utf-8"))


def open_connection(args: argparse.Namespace):
    return pymysql.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database,
        charset="utf8mb4",
        autocommit=False,
    )


def collect_repair_statements(connection, desired_comments: dict[str, dict[str, object]]) -> list[str]:
    statements: list[str] = []
    with connection.cursor() as cursor:
        for table_name, desired in desired_comments.items():
            cursor.execute(f"SHOW CREATE TABLE `{table_name}`")
            row = cursor.fetchone()
            if not row:
                continue
            show_create_table = row[1]
            statements.extend(build_comment_fix_sql(table_name, show_create_table, desired))
    return statements


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair MySQL table and column comments from resources/init.sql")
    parser.add_argument("--host", default=DEFAULT_DB_CONFIG["host"])
    parser.add_argument("--port", type=int, default=DEFAULT_DB_CONFIG["port"])
    parser.add_argument("--user", default=DEFAULT_DB_CONFIG["user"])
    parser.add_argument("--password", default=DEFAULT_DB_CONFIG["password"])
    parser.add_argument("--database", default=DEFAULT_DB_CONFIG["database"])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Print pending SQL and exit non-zero when drift exists")
    mode.add_argument("--apply", action="store_true", help="Execute repair SQL")
    args = parser.parse_args()

    desired_comments = load_desired_comments()
    connection = open_connection(args)
    try:
        statements = collect_repair_statements(connection, desired_comments)
        if not statements:
            print("Database comments are already in sync.")
            return 0

        for statement in statements:
            print(statement)

        if args.apply:
            with connection.cursor() as cursor:
                for statement in statements:
                    cursor.execute(statement)
            connection.commit()
            print(f"Applied {len(statements)} comment repair statements.")
            return 0

        print(f"Pending {len(statements)} comment repair statements.")
        return 1
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
