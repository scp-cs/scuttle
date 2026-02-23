import yaml
from logging import info, error, critical
from functools import lru_cache
from .framework import render_template_file, FrameworkError
from enum import StrEnum
from db import Frontpage
import os

MODULE_DIR = os.path.dirname(__file__)
role_cache = None

class RoleType(StrEnum):
    TRANSLATOR = 'translator'
    WRITER = 'writer'
    CORRECTOR = 'corrector'
    HELPER = 'o4'
    ADMIN = 'o5'

def load_role_file():
    global role_cache
    try:
        with open(os.path.join(MODULE_DIR, 'config', 'roles.yaml'), 'r', encoding='utf-8') as rolefile:
            # Load the config
            role_data = yaml.safe_load(rolefile)
    except Exception as e:
        critical(f"Framework error: failed to load roles ({str(e)})")
        raise FrameworkError(f"Failed to load roles ({str(e)})")
    if not isinstance(role_data, dict):
        print(role_data)
        critical(f"Framework error: malformed role configuration")
        raise FrameworkError("Malformed role configuration")
    for role_type, data in role_data.items():
        role_data[role_type].get("roles").sort(key=lambda r: r['point_limit'], reverse=True)
    role_cache = role_data

# This one doesn't strictly need to be cached as the config is only loaded once but whatever
@lru_cache(maxsize=4096)
def get_role(points: int, type: RoleType = RoleType.TRANSLATOR):
    global role_cache # Evil ass global variable 
    if role_cache is None:
        load_role_file()
    if not role_cache.get(type, None):
        error(f"No role badge configured for type \"{type}\"")
        return ""
    role_type = role_cache[type]
    if points < role_type['min_points']: return role_type['no_role']
    for role in role_type['roles']:
        if role['point_limit'] <= points:
            return role

def get_all_badges(stats: Frontpage, classes: str = "", override_classes: bool = False) -> str:
    if role_cache is None:
        load_role_file()
    combined_html = ""
    if stats.points >= role_cache['translator']['min_points']:
        combined_html += role_badge(stats.points, RoleType.TRANSLATOR, classes, override_classes)
        combined_html += " "
    if stats.original_count >= role_cache['writer']['min_points']:
        combined_html += role_badge(stats.original_count, RoleType.WRITER, classes, override_classes)
        combined_html += " "
    # Just return the blank translator role if we have no others
    if len(combined_html) == 0:
        combined_html = role_badge(0)
    return combined_html

def has_badge(stats: Frontpage, role_type: RoleType) -> bool:
    points_compared = 0
    match role_type:
        case RoleType.TRANSLATOR: points_compared = stats.points
        case RoleType.WRITER: points_compared = stats.original_count
        case _: return False
    if points_compared >= role_cache[role_type]['min_points']: return True
    return False

# Caching to not use unnecessary I/O
@lru_cache(maxsize=4096)
def role_badge(points: int, type: RoleType = RoleType.TRANSLATOR, classes: str = "", override_classes: bool = False) -> str:
    # if override_classes is true, the class list of the badge is replaced by the classes paramerer
    # if false, the contents of the classes parameter are appended to the end of the class list
    role = get_role(points, type)
    return render_template_file(os.path.join(MODULE_DIR, 'templates', 'role_badge.j2'),\
                                name=role['name'],\
                                classes=role['badge_css']+f" {classes}",\
                                override_classes=override_classes)