from __future__ import annotations

import re
from typing import Any

from .redaction import API_KEY_PREFIX_PATTERN

def is_secret_key(key: str) -> bool:
    pattern = re.compile(r'(?i)([a-z0-9_-]*(?:api[_-]?key|secret|token|bearer|password|credentials|auth|private[_-]?key))')
    return bool(pattern.search(key))

def contains_secret_value(value: str) -> bool:
    return bool(API_KEY_PREFIX_PATTERN.search(value))

def contains_absolute_path(value: str, home_dir: str) -> bool:
    if home_dir in value:
        return True
    if value.startswith("/"):
        return True
    return False

def _extract_recursive(data: Any, home_dir: str) -> Any:
    if isinstance(data, dict):
        result = {}
        for k, v in data.items():
            if is_secret_key(str(k)):
                return None
            if contains_absolute_path(str(k), home_dir):
                return None
            
            extracted_v = _extract_recursive(v, home_dir)
            if extracted_v is None:
                return None
            result[k] = extracted_v
        return result
    elif isinstance(data, list):
        result_list = []
        for item in data:
            extracted_item = _extract_recursive(item, home_dir)
            if extracted_item is None:
                return None
            result_list.append(extracted_item)
        return result_list
    elif isinstance(data, str):
        if contains_secret_value(data):
            return None
        if contains_absolute_path(data, home_dir):
            return None
        return data
    else:
        return data

def extract_preferences(config_data: dict[str, Any], family_owned_keys: set[str], home_dir: str) -> dict[str, Any]:
    preferences = {}
    
    for key, value in config_data.items():
        if key in family_owned_keys:
            continue
        
        if is_secret_key(str(key)):
            continue
        if contains_absolute_path(str(key), home_dir):
            continue
            
        extracted_value = _extract_recursive(value, home_dir)
        if extracted_value is not None:
            preferences[key] = extracted_value
            
    return preferences
