import decimal
import datetime
import mysql.connector
from src.config import Config

def get_db_connection():
    # Attempt to establish a database connection using mysql-connector
    # We do NOT use try-catch block here to suppress error, allowing database connection errors
    # (like Access Denied, Server Down, etc.) to bubble up directly.
    conn = mysql.connector.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME
    )
    return conn

def execute_query(query, params=None):
    # Execute a query and return results.
    # No try-catch blocks here. Let errors propagate directly to the caller.
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(query, params or ())
        
        # If it's a select query, fetch results
        if cursor.description:
            result = cursor.fetchall()
            # Convert Decimal, date, and datetime to serializable formats
            for row in result:
                for k, v in row.items():
                    if isinstance(v, decimal.Decimal):
                        row[k] = float(v)
                    elif isinstance(v, (datetime.date, datetime.datetime)):
                        row[k] = v.isoformat()
        else:
            conn.commit()
            result = cursor.rowcount
            
        return result
    finally:
        cursor.close()
        conn.close()
