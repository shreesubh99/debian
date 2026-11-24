import decimal
import datetime
from src.config import Config

try:
    import mysql.connector
    def get_db_connection():
        return mysql.connector.connect(
            host=Config.DB_HOST,
            port=int(Config.DB_PORT or 3306),
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            connection_timeout=10
        )
except ImportError:
    import pymysql
    import pymysql.cursors
    def get_db_connection():
        return pymysql.connect(
            host=Config.DB_HOST,
            port=int(Config.DB_PORT or 3306),
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            connect_timeout=10,
            cursorclass=pymysql.cursors.DictCursor
        )

def execute_query(query, params=None):
    # Execute a query and return results.
    conn = get_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)
    except TypeError:
        # PyMySQL already uses DictCursor
        cursor = conn.cursor()
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
