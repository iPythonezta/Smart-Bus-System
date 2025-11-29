"""
Database utility module for executing raw SQL queries.
This module provides helper functions to interact with the MySQL database
using raw SQL instead of Django's ORM.
"""

from django.db import connection
from contextlib import contextmanager


def dictfetchall(cursor):
    """
    Return all rows from a cursor as a list of dictionaries.
    """
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def dictfetchone(cursor):
    """
    Return one row from a cursor as a dictionary.
    """
    columns = [col[0] for col in cursor.description]
    row = cursor.fetchone()
    if row:
        return dict(zip(columns, row))
    return None


@contextmanager
def get_cursor():
    """
    Context manager for database cursor.
    Automatically handles connection and cleanup.
    """
    cursor = connection.cursor()
    try:
        yield cursor
    finally:
        cursor.close()


def execute_query(sql, params=None):
    """
    Execute a SELECT query and return all results as dictionaries.
    
    Args:
        sql: SQL query string
        params: Optional tuple/list of parameters for the query
    
    Returns:
        List of dictionaries representing the rows
    """
    with get_cursor() as cursor:
        cursor.execute(sql, params or [])
        return dictfetchall(cursor)


def execute_query_one(sql, params=None):
    """
    Execute a SELECT query and return a single result as dictionary.
    
    Args:
        sql: SQL query string
        params: Optional tuple/list of parameters for the query
    
    Returns:
        Dictionary representing the row, or None if not found
    """
    with get_cursor() as cursor:
        cursor.execute(sql, params or [])
        return dictfetchone(cursor)


def execute_insert(sql, params=None):
    """
    Execute an INSERT query and return the last inserted ID.
    
    Args:
        sql: SQL INSERT statement
        params: Optional tuple/list of parameters
    
    Returns:
        The ID of the newly inserted row
    """
    with get_cursor() as cursor:
        cursor.execute(sql, params or [])
        return cursor.lastrowid


def execute_update(sql, params=None):
    """
    Execute an UPDATE or DELETE query and return the number of affected rows.
    
    Args:
        sql: SQL UPDATE/DELETE statement
        params: Optional tuple/list of parameters
    
    Returns:
        Number of rows affected
    """
    with get_cursor() as cursor:
        cursor.execute(sql, params or [])
        return cursor.rowcount


def execute_many(sql, params_list):
    """
    Execute the same query with multiple sets of parameters.
    
    Args:
        sql: SQL statement
        params_list: List of tuples, each containing parameters for one execution
    
    Returns:
        Number of rows affected
    """
    with get_cursor() as cursor:
        cursor.executemany(sql, params_list)
        return cursor.rowcount
