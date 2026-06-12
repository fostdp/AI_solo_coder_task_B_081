import json
import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class ServiceSettings(BaseSettings):
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "tcm_formulas"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"
    redis_url: str = "redis://localhost:6379/0"
    api_host: str = "0.0.0.0"

    formula_loader_port: int = 8001
    pattern_miner_port: int = 8002
    drug_discoverer_port: int = 8003
    graph_api_port: int = 8004
    efficacy_scorer_port: int = 8005
    dose_response_modeler_port: int = 8006
    adverse_event_miner_port: int = 8007
    clinical_trial_integrator_port: int = 8008
    meta_analysis_service_port: int = 8009
    text_mining_worker_port: int = 8010
    gateway_port: int = 8000

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return ServiceSettings()


CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "algorithm_config.json")

_DEFAULT_CONFIG = {
    "fp_growth": {
        "min_support": 0.05,
        "min_confidence": 0.3,
        "min_lift": 1.0,
        "max_itemset_length": 3,
        "top_pairs_n": 20,
        "top_triplets_n": 20
    },
    "louvain": {
        "resolution": 1.0,
        "random_state": 42,
        "partition_size": 100,
        "min_co_occurrence": 5,
        "refine_max_iterations": 5,
        "incremental_max_iterations": 3
    },
    "link_prediction": {
        "default_method": "adamic_adar",
        "top_n": 50,
        "combined_weights": {
            "adamic_adar": 0.4,
            "jaccard": 0.3,
            "target_similarity": 0.3
        }
    },
    "graph": {
        "aggregation_threshold": 150,
        "worker_node_threshold": 50,
        "default_limit_per_type": 50,
        "co_occurs_limit": 100
    },
    "formula_search": {
        "text_index_weights": {
            "name": 10,
            "indications": 5,
            "source": 1
        },
        "default_language": "none"
    }
}


def load_algorithm_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return _DEFAULT_CONFIG


def save_algorithm_config(config: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_algorithm_config():
    cfg = load_algorithm_config()
    merged = {}
    for key, val in _DEFAULT_CONFIG.items():
        if key in cfg:
            if isinstance(val, dict):
                merged[key] = {**val, **cfg[key]}
            else:
                merged[key] = cfg[key]
        else:
            merged[key] = val
    return merged


@lru_cache()
def get_fp_growth_config():
    return get_algorithm_config()["fp_growth"]


@lru_cache()
def get_louvain_config():
    return get_algorithm_config()["louvain"]


@lru_cache()
def get_link_prediction_config():
    return get_algorithm_config()["link_prediction"]


@lru_cache()
def get_graph_config():
    return get_algorithm_config()["graph"]


def reload_config():
    load_algorithm_config.cache_clear()
    get_algorithm_config.cache_clear()
    get_fp_growth_config.cache_clear()
    get_louvain_config.cache_clear()
    get_link_prediction_config.cache_clear()
    get_graph_config.cache_clear()
