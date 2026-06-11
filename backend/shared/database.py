from pymongo import MongoClient
from neo4j import GraphDatabase
from shared.config import get_settings

_mongo_client = None
_mongo_db = None
_neo4j_driver = None


def get_mongo_db():
    global _mongo_client, _mongo_db
    if _mongo_client is None:
        settings = get_settings()
        _mongo_client = MongoClient(settings.mongodb_url)
        _mongo_db = _mongo_client[settings.mongodb_db_name]
    return _mongo_db


def get_collection(name):
    db = get_mongo_db()
    return db[name]


def get_neo4j_driver():
    global _neo4j_driver
    if _neo4j_driver is None:
        settings = get_settings()
        _neo4j_driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password)
        )
    return _neo4j_driver


def run_neo4j_query(query, parameters=None):
    driver = get_neo4j_driver()
    with driver.session() as session:
        result = session.run(query, parameters or {})
        return [record.data() for record in result]


def close_mongo():
    global _mongo_client
    if _mongo_client:
        _mongo_client.close()
        _mongo_client = None


def close_neo4j():
    global _neo4j_driver
    if _neo4j_driver:
        _neo4j_driver.close()
        _neo4j_driver = None
