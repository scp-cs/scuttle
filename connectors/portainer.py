from flask import Flask
from logging import debug, info, warning, error
from functools import wraps
from http import HTTPStatus
import requests
import urllib.parse

INVALID_STATUS_CODE = -999

class PortainerError(Exception): pass
class InvalidConfigError(PortainerError): pass
class InvalidCredentialsError(PortainerError): pass
class ServerError(PortainerError): pass

class PortainerConnector():
    """
    An API connector for portainer. Class instance is bound to a single container as the intended purpose is to start/kill and monitor the wikicomma container during a backup.

    Loads configuration from app config using init_app(), config should be formatted like this:

    ```txt
    [config_root] {
        BACKUP {
            PORTAINER {
                URL: API URL - see init_app()
                USER: Username
                PASSWORD: Password
                ENV_ID: Portainer environment ID. Should be 1 if you're only running locally, check GUI
                CONTAINER_NAME: The container's name
            }
        }
    }
    ```
    """
    __initialized = False

    def requires_init(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if not getattr(self, '__initialized', False):
                raise PortainerError("Not Initialized")
            return func(self, *args, **kwargs)
        return wrapper
    
    def requires_auth(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if getattr(self, 'url', None) == None:
                raise PortainerError('No Portainer URL')
            if not hasattr(self, '_jwt'):
                raise PortainerError(f"Not logged in")
            return PortainerConnector.requires_init(func(self, *args, **kwargs))
        return wrapper

    def init_app(self, app: Flask):
        """
        PORTAINER_URL should be in this format: "https://portainer.xyz/api"
        i.e. WITH the api endpoint and WITHOUT a trailing slash
        """

        debug('PortainerConnector initializing')

        if 'PORTAINER' not in app.config['BACKUP']:
            warning('Portainer config not found')
            raise InvalidConfigError('Portainer config not found')

        config = app.config['BACKUP']['PORTAINER']

        if 'URL' not in config:
            warning('Portainer API URL not found')
            raise InvalidConfigError('Portainer API URL not found')

        if 'PASSWORD' not in config or 'USER' not in config:
            warning('Portainer credentials not found')
            raise InvalidConfigError('Portainer credentials not found')

        if 'ENV_ID' not in config:
            warning('Portainer environment ID not found')
            raise InvalidConfigError('Portainer environment ID not found')

        if 'CONTAINER_NAME' not in config:
            warning('Portainer container name not found')
            raise InvalidConfigError('Portainer container name not found')
        
        self.url = config['URL']
        self.__user = config['USER']
        self.__password = config['PASSWORD']
        self.__env_id = config['ENV_ID']
        self.__container_name = config['CONTAINER_NAME']
        self.__initialized = True

        debug('PortainerConnector init complete')

    def get_name(self) -> str:
        return self.__container_name

    def is_initialized(self) -> bool:
        """
        Returns true if all necessary config values are present and loaded
        """
        return self.__initialized

    @requires_init
    def login(self, user: str = None, password: str = None):
        """
        Logs in to portainer and saves the access token. If no credentials are specified, those loaded from config are used.
        """

        username = self.__user or user
        password = self.__password or password

        if not username or not password:
            error("Can't login, no credentials")
            raise InvalidCredentialsError("Can't login, no credentials")
        
        if not self.url:
            error("Can't login, no url set")
            raise InvalidConfigError("Can't login, no url set")

        login_response = requests.post(self.url+'/auth', json={'Username': username, "Password": password})
        match login_response.status_code:
            case HTTPStatus.UNPROCESSABLE_ENTITY: # Don't ask me why portainer sends a 422 instead of 401
                error('Invalid credentials')
                raise InvalidCredentialsError('Login failed, invalid credentials')
            case HTTPStatus.OK:
                info('Login success')
                self._jwt = login_response.json()['jwt']
                return
            case _:
                error(f'Weird status code from portainer ({login_response.status_code} - {HTTPStatus(login_response.status_code).name})')
                raise PortainerError(f'Weird status code from portainer ({login_response.status_code} - {HTTPStatus(login_response.status_code).name})')

    @requires_auth
    def __find_container(self) -> str:
        filters = urllib.parse.quote(f'{{"name": ["{self.__container_name}"]}}')
        query_url = self.url+f'/endpoints/{self.__env_id}/docker/containers/json?all=true&filters={filters}'

        response = requests.get(query_url, headers={"Authorization": f"Bearer {self._jwt}"})
        if response.status_code != HTTPStatus.OK:
            error(f"Portainer request failed, got status code {response.status_code}")
            raise PortainerError(f"Portainer request failed, got status code {response.status_code}")

        json = response.json()
        if len(json) != 1:
            raise PortainerError(f"Got multiple containers or none at all")

        return json[0]['Id']

    @requires_auth
    def __container_action(self, action: str):
        container_id = self.__find_container()
        query_url = self.url+f'/endpoints/{self.__env_id}/docker/containers/{container_id}/{action}'
        return requests.post(query_url, headers={"Authorization": f"Bearer {self._jwt}"})

    @requires_auth
    def start_container(self):
        """
        Starts the container. Does nothing if container is already running.
        """

        response = self.__container_action('start')
        match response.status_code:
            case HTTPStatus.NO_CONTENT: # Portainer at it with the silly status codes again 
                info("Container successfully started")
            case HTTPStatus.NOT_MODIFIED: # Okay I guess this one makes sense
                warning("Container is already running")
            case HTTPStatus.INTERNAL_SERVER_ERROR:
                error("Couldn't start container")
                raise PortainerError("Couldn't start container, server error")

    @requires_auth
    def stop_container(self):
        """
        Stops the container. Does nothing if container is not running.
        """
        response = self.__container_action('stop')
        match response.status_code:
            case HTTPStatus.NO_CONTENT:
                info("Container successfully stopped")
            case HTTPStatus.NOT_MODIFIED:
                warning("Container is not running")
            case HTTPStatus.INTERNAL_SERVER_ERROR:
                error("Couldn't stop container")
                raise PortainerError("Couldn't stop container, server error")
        
    @requires_auth
    def kill_container(self):
        """
        Forcefully stops the container (SIGKILL). Does nothing if container is not running.
        """
        response = self.__container_action('kill')
        match response.status_code:
            case HTTPStatus.NO_CONTENT:
                info("Container killed")
            case HTTPStatus.CONFLICT:
                warning("Container is not running")
            case HTTPStatus.INTERNAL_SERVER_ERROR:
                error("Couldn't kill container")
                raise PortainerError("Couldn't kill container, server error")

    @requires_auth
    def restart_container(self):
        """
        Restarts a container. I don't actually know whether this starts the container if not running.
        """
        response = self.__container_action('restart')
        match response.status_code:
            case HTTPStatus.NO_CONTENT:
                info("Container restarted")
            case HTTPStatus.INTERNAL_SERVER_ERROR:
                error("Couldn't restart container")
                raise PortainerError("Couldn't restart container, server error")
    
    @requires_auth
    def wait_for_exit(self) -> int:
        """Blocks the current thread until the container exits

        Returns:
            int: The container's exit code, -999 if the command fails
        """
        container_id = self.__find_container()
        query_url = self.url+f'/endpoints/{self.__env_id}/docker/containers/{container_id}/wait'
        info('Waiting for container to exit')
        response = requests.post(query_url, headers={"Authorization": f"Bearer {self._jwt}"}, timeout=None)

        match response.status_code:
            case HTTPStatus.OK:
                info('Container exited')
                return response.json()['StatusCode']
            case _:
                error('Got unusual status code while waiting for exit')
                return INVALID_STATUS_CODE