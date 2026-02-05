# Builtins
import json
from logging import info, warning, error, debug, critical
import logging
from os import environ as env, makedirs

# External
from flask import Flask, render_template, request
from werkzeug.serving import is_running_from_reloader
from flask_login import current_user
from waitress import serve

# Internal
from crypto import pw_hash
from connectors.discord import DiscordClient
from connectors.rss import RSSUpdateType
from framework.menu import navigation_menu
from framework.roles import role_badge
from utils import ensure_config
from tasks import discord_tasks, backup_task
from db import User
from crypto import generate_signing_keys
import db

# Blueprints
from blueprints.auth import UserAuth
from blueprints.debug import DebugTools
from blueprints.content import UserContent
from blueprints.errorhandler import ErrorHandler
from blueprints.users import UserController
from blueprints.articles import ArticleController
from blueprints.stats import StatisticsController
from blueprints.api import ApiController
from blueprints.rsspage import RssPageController
from blueprints.oauth import OauthController
from blueprints.autobackup import AutobackupController
from blueprints.embed import EmbedController

from extensions import login_manager, sched, oauth, rss, webhook, portainer
from constants import APP_VERSION

app = Flask(__name__)

LOGGER_FORMAT_STR = '[%(asctime)s][%(module)s] %(levelname)s: %(message)s'

@app.route('/')
def index():
    sort = request.args.get('sort', type=str, default='points')
    page = request.args.get('p', type=int, default=0)
    user_count = User.select().count()
    return render_template('users.j2', users=db.get_frontpage(sort, page), lastupdate=db.last_update().strftime("%Y-%m-%d %H:%M:%S"), user_count=user_count, sort=sort)

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

    login_manager.session_protection = "basic"
    login_manager.login_view = "UserAuth.login"
    login_manager.login_message = u"Pro zobrazení této stránky se přihlaste"
    login_manager.user_loader(lambda uid: User.get_by_id(uid))
    login_manager.init_app(app)

    # Checking if we can enable Discord Login
    appid, appsecret = app.config.get('DISCORD_CLIENT_ID', None), app.config.get('DISCORD_CLIENT_SECRET', None)
    app.config['OAUTH_ENABLE'] = app.config.get('DISCORD_LOGIN_ENABLE', True)
    if not appid or not appsecret:
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
    discord_token = app.config.get('DISCORD_TOKEN', None)
    if discord_token:
        DiscordClient.init_app(app)
        sched.add_job('Download avatars', lambda: discord_tasks.download_avatars_task(), trigger='interval', days=3)
        sched.add_job('Fetch nicknames', lambda: discord_tasks.update_nicknames_task(), trigger='interval', days=4)
    else:
        warning('Discord API token not set. Profiles won\'t be updated!')

    if app.config.get('BACKUP', {}).get('BACKUP_INTERVAL') is not None:
        sched.add_job('autobackup_run', lambda: backup_task.run_backup_task(app.config['BACKUP']['BACKUP_INTERVAL'], app), trigger='interval', hours=12)

    # Checking if we have a webhook URL
    webhook_url = app.config.get('DISCORD_WEBHOOK_URL', None)
    if webhook_url:
        webhook.init_app(app)
        app.config['WEBHOOK_ENABLE'] = True
    else:
        app.config['WEBHOOK_ENABLE'] = False

    rss.init_app(app)

    # Checking if we have any RSS feeds configured
    if rss.has_links:
        sched.add_job('Fetch RSS updates', rss.check, trigger='interval', hours=1)

    # Check if Portainer config is present
    if 'BACKUP' in app.config and 'PORTAINER' in app.config['BACKUP']:
        portainer.init_app(app)

# TODO: App factory??
if __name__ == '__main__':
    init_logger()

    # Load config file or create it if there isn't one
    if not ensure_config('config.json') or not app.config.from_file('config.json', json.load):
        critical("Config file is inaccessible, malformed or could not be created")
        exit(1)

    # Set debug logging level before doing anything else
    if app.config['DEBUG']:
        logging.getLogger().setLevel(logging.DEBUG)

    # Ensure we have a directory to store the avatar thumbnails
    makedirs('./temp/avatar', exist_ok=True)

    # Create a data directory if it doesn't exist
    # Regular mkdir doesn't have the exist_ok option for whatever reason
    makedirs('./data', exist_ok=True)

    # Store all the singleton classes in config to access them from blueprints
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
    
    # Load all the blueprints
    app.register_blueprint(ErrorHandler)
    app.register_blueprint(UserContent)
    app.register_blueprint(UserAuth)
    app.register_blueprint(DebugTools)
    app.register_blueprint(UserController)
    app.register_blueprint(ArticleController)
    app.register_blueprint(StatisticsController)
    app.register_blueprint(ApiController)
    app.register_blueprint(OauthController)
    app.register_blueprint(RssPageController)
    app.register_blueprint(AutobackupController)
    app.register_blueprint(EmbedController)

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
        app.run('0.0.0.0', 8080)
    else:
        fix_proxy()
        info("Init complete. Starting WSGI server now.")
        serve(app, threads=64)