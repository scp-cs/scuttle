# Builtins
import json
import time
import typing as t
from logging import warning, error, info, debug
from flask import current_app
from http import HTTPStatus

# External
import requests

API_UA = "SCUTTLE Discord service (https://scp-wiki.cz, v1)"
API_URL = "https://discord.com/api/v10"
CDN_URL = "https://cdn.discordapp.com"

RATELIMIT_RETRIES = 3

class DiscordException(Exception):
    pass

# TODO: Store app object and use instead of current_app

class DiscordClient():

    def __new__(*args, **kwargs):
        # Pretend python has static classes and this is one
        raise TypeError("Static class cannot be instantiated")

    @staticmethod
    def init_app(app):
        auth_token = app.config.get('DISCORD_TOKEN', "")
        DiscordClient.__auth_token = auth_token
        DiscordClient.__request_headers = {
            "User-Agent": API_UA,
            "Authorization": f"Bot {DiscordClient.__auth_token}",
            "Content-Type": "application/json"
        }

    @staticmethod
    def _validate_user_id(uid: str):
        if len(uid) not in [18, 19]:
            return False
        try:
            _ = int(uid)
        except Exception:
            return False
        return True
    
    @staticmethod
    def get_user(uid: int) -> t.Optional[dict]:
        
        retry = 0
        while retry < RATELIMIT_RETRIES:
            response = requests.get(API_URL + f'/users/{uid}', headers=DiscordClient.__request_headers)
            if response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
                wait_sec = 2**retry
                warning(f"Rate limited! Waiting for {wait_sec}")
                time.sleep(wait_sec)
                retry += 1
            else:
                break

        if response.status_code == HTTPStatus.OK:
            return json.loads(response.content)
        elif response.status_code == HTTPStatus.NOT_FOUND:
            warning(f'Discord user API returned 404 for {uid}')
            return None
        else:
            error(f'Discord API request failed for {uid}')
            raise DiscordException("API Request failed")

    @staticmethod
    def get_global_username(uid: int) -> t.Optional[str]:
        """Fetches the global nickname, if the user doesn't have any set, returns the username

        Args:
            uid (int): The user's Discord ID

        Raises:
            DiscordException: Raised when either of the API requests fails

        Returns:
            str | None - The nickname / username. None is returned if the request succeeds but some other unexpected error occurs
        """
        
        try:
            user = DiscordClient.get_user(uid)
        except DiscordException as e:
            raise e
        if user is None:
            return None
        if user['global_name'] == None:
            return user['username']
        return user['global_name']

    @staticmethod
    def get_avatar(uid: int, size = 256) -> bytes:
        """Fetches the avatar of a user from Discord's CDN. Results are cached for 6 hours.

        Args:
            uid (int): The user's Discord ID
            size (int): The avatar's size, defaults to 512 px

        Raises:
            DiscordException: Raised when either of the API requests fails

        Returns:
            bytes: A bytes object containing the user's avatar in PNG format
        """
        try:
            user = DiscordClient.get_user(uid)
        except DiscordException as e:
            raise e

        if user is None:
            return None

        endpoint = CDN_URL + f"/avatars/{uid}/{user['avatar']}.png"
        
        retry = 0
        while retry < RATELIMIT_RETRIES:
            response = requests.get(endpoint, headers=DiscordClient.__request_headers, params={'size': str(size)})
            if response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
                wait_sec = 2**retry
                warning(f"Rate limited! Waiting for {wait_sec}")
                time.sleep(wait_sec)
                retry += 1
            else:
                break

        if response.status_code == HTTPStatus.OK:
            return response.content
        elif response.status_code == HTTPStatus.NOT_FOUND:
            warning(f"Discord CDN request returned 404 for {uid}")
            return None
        else:
            error(f"Discord CDN request failed for {uid}")
            raise DiscordException("CDN Request failed")

class DiscordWebhook():
    """
    Utility class for sending webhooks
    """
    def __init__(self, url: str = None, notify = 0) -> None:
        self.url = url
        self.notify = notify

    def init_app(self, app):
        self.url = app.config['WEBHOOK']['WEBHOOK_URL']
        self.notify = app.config['DISCORD_ROLEMASTER_ID']
        self.mock = app.config.get("DEBUG_DISABLE_WEBHOOKS", False) and app.config.get("DEBUG", False)

    def send_text(self, message: str, ping_user: int = 0) -> None:
        if not self.url:
            raise RuntimeError('Cannot send an uninitialized webhook (no URL specified)')
        if self.mock:
            debug(f"Mock send webhook with message \"{message}\" with ping for {self.notify or ping_user or '[nobody]'}")
            return
        if current_app.config['DEBUG'] == True:
            message = f"[TESTOVACÍ REŽIM - PROSÍM IGNORUJTE] {message}"
        if len(message) > 2000:
            raise ValueError(f'Message is too long ({len(message)} characters)')
        if ping_user:
            data = {"content": f'<@{ping_user}> {message}'}
        elif self.notify:
            data = {"content": f'<@{self.notify}> {message}'}
        else:
            data = {"content": message}
        info('Sending webhook')
        try:
            webhook_response = requests.post(self.url, json=data)
        except Exception as e:
            error(f'Webhook failed to send ({str(e)})')
