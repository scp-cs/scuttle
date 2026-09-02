# Builtins
from enum import IntFlag
from functools import wraps
from typing import cast
from logging import info, error, critical
import os

# External
from flask_login import current_user
from flask import abort, request, Flask
import yaml

# Internal
from db import User
from .framework import FrameworkError

class UserPermission(IntFlag):
    MASTER_ADMIN = 1            # All the permissions below
    MANAGE_ARTICLE_SELF = 2     # Create / Edit / Delete articles authored by user's ID
    MANAGE_ARTICLE_ALL = 4      # Create / Edit / Delete any article
    MANAGE_USERS = 8            # Create / Edit / Delete users
    DEBUG_LOW = 16              # Run safe debug commands
    DEBUG_HIGH = 32             # Run unsafe debug commands
    VIEW_BACKUPS = 64           # List backups, download archives and signatures
    MANAGE_BACKUPS = 128        # Reconfigure and run WikiComma, delete backups
    MANAGE_BOT = 256            # Send commands to the discord bot
    ACCESS_RSS = 512            # View the new pages pulled from RSS
    ADMIN = 1024                # General permissions for branch admins
    API = 2048                  # Create API keys

_IMPLICIT_PERMISSION = {
                        UserPermission.ADMIN: UserPermission.MANAGE_ARTICLE_ALL | UserPermission.MANAGE_USERS\
                              | UserPermission.VIEW_BACKUPS | UserPermission.ACCESS_RSS,
                        UserPermission.MANAGE_ARTICLE_ALL: UserPermission.MANAGE_ARTICLE_SELF,
                        UserPermission.DEBUG_HIGH: UserPermission.DEBUG_LOW,
                        UserPermission.MANAGE_BACKUPS: UserPermission.VIEW_BACKUPS,
                        }

class ACLManager:

    def __init__(self):
        self._lists = {}

    def _perm_check_handler(self):

        blueprint_id = request.blueprint
        bp_lists = self._lists.get(blueprint_id, None)

        if not bp_lists:
            # ACL not configured for this blueprint
            return

        endpoint_name = request.endpoint.split('.')[-1]

        if endpoint_name not in bp_lists:
            # ACL not configured for this endpoint
            return

        if not current_user or current_user.is_anonymous or not current_user.is_authenticated:
            abort(403)

        current_perms = UserPermission(current_user.permissions)
        full_perms = ACLManager._expand_permissions(current_perms)

        if UserPermission.MASTER_ADMIN in full_perms:
            # MA overrides everything else
            return

        required_perms = [UserPermission[perm] for perm in bp_lists[endpoint_name]]
        
        if not all(p in full_perms for p in required_perms):
            abort(403)

    def _load_config(self):
        try:
            current_dir = os.path.dirname(__file__)
            with open(os.path.join(current_dir, 'config', 'acl.yaml'), 'r', encoding='utf-8') as aclfile:
                # Load the config
                self._lists = yaml.safe_load(aclfile)['lists']
        except Exception as e:
            critical(f"Framework error: Couldn't load access control lists ({e!r})")
            raise FrameworkError(f"Couldn't load access control lists ({e!r})")

        endpoint_count = 0

        for bp in self._lists.values():
            for endpoint in bp.values():
                for perm in endpoint:
                    try:
                        _ = UserPermission[perm]
                        endpoint_count += 1
                    except KeyError:
                        critical(f"Invalid permission: \"{perm}\"")
                        raise FrameworkError(f"Invalid configuration: role {perm} doesn't exist")

        info(f"Loaded ACL lists for {endpoint_count} endpoints")
        
    def init_app(self, app: Flask):
        self.app = app
        self._load_config()
        app.before_request(self._perm_check_handler)

    @staticmethod
    def get_permission_color_class(perms: UserPermission):
        match perms:
            case UserPermission.MASTER_ADMIN:
                return 'bg-red-400/5 border-red-400/20 text-red-400'
            case UserPermission.DEBUG_HIGH | UserPermission.DEBUG_LOW:
                return 'bg-blue-400/5 border-blue-400/20 text-blue-400'
            case UserPermission.MANAGE_ARTICLE_SELF | UserPermission.MANAGE_ARTICLE_ALL | UserPermission.MANAGE_USERS:
                return 'bg-orange-400/5 border-orange-400/20 text-orange-400'
            case UserPermission.MANAGE_BACKUPS | UserPermission.VIEW_BACKUPS:
                return 'bg-pink-400/5 border-pink-400/20 text-pink-400'
            case _: return 'bg-green-400/5 border-green-400/20 text-green-400'

    @staticmethod
    def _expand_permissions(perms: UserPermission) -> UserPermission:
        for permission in perms:
            perms |= _IMPLICIT_PERMISSION.get(permission, 0)
        return perms

    @staticmethod
    def check_permission(perm: UserPermission, user: User | None = None):
        target = user or current_user

        if target.is_anonymous or not target.is_authenticated:
            return False

        # Peewee's developer hates typing so we have to cast shii
        perm_flags = ACLManager._expand_permissions(UserPermission(cast(int, target.permissions)))

        # Master admin perm overrides everything else
        if UserPermission.MASTER_ADMIN in perm_flags:
            return True

        return perm in perm_flags