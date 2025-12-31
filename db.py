import mysql.connector
from mysql.connector import Error

def get_db_connection():
    try:
        db=mysql.connector.connect(
            host="localhost",
            user="root",
            password="112233",
            database="hospitaldb"
        )
        return db
    except Error as e:
        print("Database connection error:",e)
        return None
