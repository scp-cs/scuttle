# Builtins
import json
from logging import info, warning, error, critical
import logging
from os import environ as env, makedirs, path, getcwd

# External
from flask import Flask
from werkzeug.serving import is_running_from_reloader
from flask_login import current_user
from waitress import serve

# Internal
from crypto import pw_hash
from connectors.discord import DiscordClient
from connectors.rss import RSSUpdateType
from framework.menu import navigation_menu
from framework.roles import role_badge
from utils import ensure_config, config_has_key
from tasks import discord_tasks, backup_task
from db import User
from crypto import generate_signing_keys
import db
from constants import APP_VERSION

# Blueprints
from blueprints.auth import AuthController
from blueprints.debug import DebugToolsController
from blueprints.content import ContentController
from blueprints.errorhandler import ErrorPageController
from blueprints.users import UserController
from blueprints.articles import ArticleController
from blueprints.stats import StatisticsController
from blueprints.api import ApiController
from blueprints.rsspage import RssPageController
from blueprints.oauth import OauthController
from blueprints.autobackup import AutobackupController
from blueprints.embed import EmbedController
from blueprints.leaderboard import LeaderboardController

from extensions import login_manager, sched, oauth, rss, webhook, portainer

app = Flask(__name__)

LOGGER_FORMAT_STR = '[%(asctime)s][%(module)s] %(levelname)s: %(message)s'

def init_logger() -> None:
    """
    Sets up logging
    """
    logging.getLogger().handlers.clear()
    logging.basicConfig(filename='translatordb.log', filemode='a', format=LOGGER_FORMAT_STR, encoding='utf-8')
    logging.getLogger().setLevel(logging.INFO)
    handler_st = logging.StreamHandler()
    handler_st.setFormatter(logging.Formatter(LOGGER_FORMAT_STR))
    logging.getLogger().addHandler(handler_st)

def fix_proxy() -> None:
    """
    Registers the ProxyFix middleware as described in https://flask.palletsprojects.com/en/3.0.x/deploying/proxy_fix/
    """
    
    if "FIX_PROXY" in app.config and app.config['FIX_PROXY']:
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
        info("Registered ProxyFix middleware")

def user_init() -> None:
    """
    Registers an administrator from environment variables
    """

    init_user, init_password = env.get("SCP_INIT_USER"), env.get("SCP_INIT_PASSWORD")
    if not init_user:
        return
    if not init_password:
        error(f"Password not specified for {init_user}")
        exit(1)
    if User.get_or_none(User.nickname == init_user) is not None:
        warning(f"Initial user {init_user} already exists")
        return
    info(f"Adding initial user {init_user}")
    admin = User()
    admin.nickname = init_user
    admin.password = pw_hash(init_password)
    # TODO: Do something with this id
    admin.discord = ""
    admin.wikidot = ""
    admin.save()

def extensions_init() -> None:
    """
    Checks which integrations can be enabled, initializes all flask extensions and schedules background tasks
    """

    # Set up login manager
    login_manager.session_protection = "basic"
    login_manager.login_view = "AuthController.login"
    login_manager.login_message = u"Pro zobrazení této stránky se přihlaste"
    login_manager.user_loader(lambda uid: User.get_by_id(uid))
    login_manager.init_app(app)

    # Checking if we can enable Discord Login
    if config_has_key(app.config, 'DISCORD.CLIENT_ID') and config_has_key(app.config, 'DISCORD.CLIENT_SECRET'):
        app.config['OAUTH_ENABLE'] = app.config['DISCORD'].get('LOGIN_ENABLE')
    else:
        warning('OAuth App ID or secret not set, Discord login disabled')
        app.config['OAUTH_ENABLE'] = False

    if app.config['OAUTH_ENABLE']:
        oauth.init_app(app)

    # Check if we are running inside Flask's auto reloader yet
    # This doesn't matter when deployed but can break things when debugging
    if is_running_from_reloader() or not app.config['DEBUG']:
        sched.init_app(app)
        sched.start()

    # Checking if we can enable the API connection
    if config_has_key(app.config, 'DISCORD.TOKEN'):
        DiscordClient.init_app(app)
        sched.add_job('Download avatars', lambda: discord_tasks.download_avatars_task(), trigger='interval', days=3)
        sched.add_job('Fetch nicknames', lambda: discord_tasks.update_nicknames_task(), trigger='interval', days=4)
    else:
        warning('Discord API token not set. Profiles won\'t be updated!')

    if app.config.get('BACKUP', {}).get('BACKUP_INTERVAL') is not None:
        sched.add_job('autobackup_run', lambda: backup_task.run_backup_task(app.config['BACKUP']['BACKUP_INTERVAL'], app), trigger='interval', hours=12)

    # Checking if we have a webhook URL
    if config_has_key(app.config, 'WEBHOOK.WEBHOOK_URL') and config_has_key(app.config, 'DISCORD_ROLEMASTER_ID'):
        webhook.init_app(app)
        app.config['WEBHOOK_ENABLE'] = True
    else:
        app.config['WEBHOOK_ENABLE'] = False

    rss.init_app(app)

    # Checking if we have any RSS feeds configured
    if rss.has_links:
        sched.add_job('Fetch RSS updates', rss.check, trigger='interval', hours=1)

    # Check if Portainer config is present
    if config_has_key(app.config, 'BACKUP.PORTAINER'):
        portainer.init_app(app)

def create_directories(app: Flask) -> None:
    """
    Creates all directories needed for the app
    """
    info("Creating directories")

    current_dir = getcwd()

    # Ensure we have a directory to store the avatar thumbnails
    makedirs(path.join(current_dir, 'temp', 'avatar'), exist_ok=True)

    # Ensure we have a directory to store original site snapshots
    makedirs(path.join(current_dir, 'temp', 'snapshots'), exist_ok=True)

    # Make snapshot directories for each source wiki
    if 'MONITORED_WIKIS' in app.config and config_has_key(app.config, "BACKUP.save_snapshots", True):
        for wiki in app.config['MONITORED_WIKIS']:
            makedirs(path.join(current_dir, 'temp', 'snapshots', wiki['source_wiki']), exist_ok=True)

    # Create a data directory if it doesn't exist
    # Regular mkdir doesn't have the exist_ok option for whatever reason
    makedirs(path.join(current_dir, 'data'), exist_ok=True)

def register_blueprints(app: Flask) -> None:
    # Load all the blueprints
    app.register_blueprint(LeaderboardController)
    app.register_blueprint(ErrorPageController)
    app.register_blueprint(ContentController)
    app.register_blueprint(AuthController)
    app.register_blueprint(DebugToolsController)
    app.register_blueprint(UserController)
    app.register_blueprint(ArticleController)
    app.register_blueprint(StatisticsController)
    app.register_blueprint(ApiController)
    app.register_blueprint(OauthController)
    app.register_blueprint(RssPageController)
    app.register_blueprint(AutobackupController)
    app.register_blueprint(EmbedController)

# TODO: App factory??
if __name__ == '__main__':
    init_logger()

    # Set debug logging level before doing anything else
    if app.config['DEBUG']:
        logging.getLogger().setLevel(logging.DEBUG)

    info(f"SCUTTLE v{APP_VERSION} starting up")

    # Load config file or create it if there isn't one
    if not ensure_config('config.json') or not app.config.from_file('config.json', json.load):
        critical("Config file is inaccessible, malformed or could not be created")
        exit(1)

    create_directories(app)

    # Store all the singleton classes in config to access them from blueprints
    # TODO: There has to be a better way to do this
    app.config['scheduler'] = sched
    app.config['oauth'] = oauth
    app.config['rss'] = rss
    app.config['webhook'] = webhook

    # Add useful template globals
    app.add_template_global(current_user, 'current_user')
    app.add_template_global(RSSUpdateType)
    app.add_template_global(navigation_menu)
    app.add_template_global(role_badge)
    app.add_template_global(APP_VERSION, 'APP_VERSION')

    register_blueprints(app)

    # Initialize the database
    db.database.connect()
    db.database.create_tables(db.models)
    db.create_views(db.database)

    # Create the admin user
    user_init()

    # Generate signing keys
    if not generate_signing_keys():
        critical("Error while generating signing keys. Exiting...")
        exit(1)

    # Load extensions and enable integrations based on config
    extensions_init()

    # Force oauthlib to allow insecure transport when debugging
    if app.config['DEBUG']:
        warning('App running in debug mode!')
        env['OAUTHLIB_INSECURE_TRANSPORT'] = 'true'
        warning('OAUTHLIB insecure transport is enabled!')
        app.run('0.0.0.0', 8080, debug=True)
    else:
        fix_proxy()
        info("Init complete. Starting WSGI server now.")
        serve(app, threads=64)