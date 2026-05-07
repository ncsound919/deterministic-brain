"""Database client tools — SQL execution and schema inspection."""
from __future__ import annotations
import os
import json
import logging
from typing import Any, Dict, List, Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class DatabaseClient:
    """Unified client for SQL databases (SQLite, PostgreSQL, MySQL)."""

    def __init__(self, db_type: str, connection_params: Dict[str, Any]):
        self.db_type = db_type.lower()
        self.connection_params = connection_params
        self._connection = None

    def connect(self) -> bool:
        """Establish database connection."""
        try:
            if self.db_type == "sqlite":
                import sqlite3
                db_path = self.connection_params.get("database", ":memory:")
                self._connection = sqlite3.connect(db_path)
                logger.info(f"Connected to SQLite: {db_path}")
                return True
            
            elif self.db_type == "postgresql":
                import psycopg2
                self._connection = psycopg2.connect(
                    host=self.connection_params.get("host", "localhost"),
                    port=self.connection_params.get("port", 5432),
                    database=self.connection_params.get("database"),
                    user=self.connection_params.get("user"),
                    password=self.connection_params.get("password"),
                )
                logger.info(f"Connected to PostgreSQL: {self.connection_params.get('database')}")
                return True
            
            elif self.db_type == "mysql":
                import pymysql
                self._connection = pymysql.connect(
                    host=self.connection_params.get("host", "localhost"),
                    port=self.connection_params.get("port", 3306),
                    database=self.connection_params.get("database"),
                    user=self.connection_params.get("user"),
                    password=self.connection_params.get("password"),
                )
                logger.info(f"Connected to MySQL: {self.connection_params.get('database')}")
                return True
            
            else:
                logger.error(f"Unsupported database type: {self.db_type}")
                return False
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False

    def disconnect(self) -> None:
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.info("Disconnected from database")

    def execute(self, query: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute a SQL query."""
        if not self._connection:
            return {"error": "Not connected to database"}
        
        try:
            cursor = self._connection.cursor()
            cursor.execute(query, params or {})
            
            if query.strip().upper().startswith(("SELECT", "SHOW", "DESCRIBE", "EXPLAIN")):
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                rows = cursor.fetchall()
                return {
                    "success": True,
                    "columns": columns,
                    "rows": rows,
                    "row_count": len(rows)
                }
            else:
                self._connection.commit()
                return {
                    "success": True,
                    "affected_rows": cursor.rowcount
                }
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            return {"success": False, "error": str(e)}

    def get_schema(self) -> Dict[str, Any]:
        """Get database schema information."""
        if not self._connection:
            return {"error": "Not connected to database"}
        
        try:
            if self.db_type == "sqlite":
                cursor = self._connection.cursor()
                cursor.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view')")
                tables = [{"name": r[0], "type": r[1]} for r in cursor.fetchall()]
                
                schema = {"tables": [], "views": []}
                for t in tables:
                    cursor.execute(f"PRAGMA table_info({t['name']})")
                    columns = [{"name": c[1], "type": c[2]} for c in cursor.fetchall()]
                    if t["type"] == "table":
                        schema["tables"].append({"name": t["name"], "columns": columns})
                    else:
                        schema["views"].append({"name": t["name"], "columns": columns})
                return schema
            
            elif self.db_type == "postgresql":
                cursor = self._connection.cursor()
                cursor.execute("""
                    SELECT table_name, table_type 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """)
                tables = [{"name": r[0], "type": r[1]} for r in cursor.fetchall()]
                
                schema = {"tables": [], "views": []}
                for t in tables:
                    cursor.execute(f"""
                        SELECT column_name, data_type 
                        FROM information_schema.columns 
                        WHERE table_name = '{t['name']}'
                    """)
                    columns = [{"name": c[0], "type": c[1]} for c in cursor.fetchall()]
                    if t["type"] == "BASE TABLE":
                        schema["tables"].append({"name": t["name"], "columns": columns})
                    else:
                        schema["views"].append({"name": t["name"], "columns": columns})
                return schema
            
            return {"error": f"Schema not implemented for {self.db_type}"}
        except Exception as e:
            return {"error": str(e)}


def db_connect(db_type: str, host: Optional[str] = None, port: Optional[int] = None,
               database: Optional[str] = None, user: Optional[str] = None,
               password: Optional[str] = None) -> Dict[str, Any]:
    """Connect to a database.
    
    Args:
        db_type: One of "sqlite", "postgresql", "mysql"
        host: Database host (not needed for sqlite)
        port: Database port (default varies by type)
        database: Database name
        user: Database user
        password: User password
    
    Returns:
        Connection status and session info
    """
    params = {"host": host, "port": port, "database": database, "user": user, "password": password}
    client = DatabaseClient(db_type, {k: v for k, v in params.items() if v is not None})
    success = client.connect()
    return {"connected": success, "db_type": db_type, "database": database}


def db_execute(query: str, params: Optional[Dict] = None) -> Dict[str, Any]:
    """Execute a SQL query on the connected database.
    
    Args:
        query: SQL query to execute
        params: Optional query parameters
    
    Returns:
        Query results
    """
    global _db_client
    if _db_client is None:
        return {"error": "No database connected"}
    return _db_client.execute(query, params)


def db_schema() -> Dict[str, Any]:
    """Get the schema of the connected database.
    
    Returns:
        Database schema with tables and columns
    """
    global _db_client
    if _db_client is None:
        return {"error": "No database connected"}
    return _db_client.get_schema()


def db_disconnect() -> Dict[str, Any]:
    """Disconnect from the current database.
    
    Returns:
        Disconnect status
    """
    global _db_client
    if _db_client:
        _db_client.disconnect()
        _db_client = None
        return {"disconnected": True}
    return {"disconnected": True}


_db_client: Optional[DatabaseClient] = None


def _set_client(client: DatabaseClient) -> None:
    global _db_client
    _db_client = client