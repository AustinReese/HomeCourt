import psycopg2
from config import environ

def getConn():
    if environ['container'] == 'false':
        return psycopg2.connect(
            database="postgres",
            user="postgres"
        )
    else:
        return psycopg2.connect(
            host='postgres',
            database="postgres",
            user="postgres"
        )