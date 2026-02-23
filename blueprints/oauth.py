from flask import flash, Blueprint, redirect, url_for, request
from flask_login import login_user
from oauthlib.oauth2.rfc6749.errors import OAuth2Error
from logging import error, warning, info

from extensions import oauth
from db import User

OauthController = Blueprint('OauthController', __name__)

@OauthController.route('/oauth/session')
def oauth_session():
    return oauth.create_session(prompt=False)

@OauthController.route('/oauth/callback')
def oauth_callback():

    try:
        oauth.callback()
        user_id = oauth.fetch_user().id
    except OAuth2Error as e:
        error(f'Oauth Failed: {str(e)}')
        flash('Autentizace selhala, zkuste to prosím znovu.')
        return redirect(url_for('AuthController.login'))
    
    user = User.get_or_none(User.discord == user_id)
    if not user:
        warning(f'Login attempt with unregistered ID {user_id} from {request.remote_addr}')
        flash('Uživatel není registrován nebo má neplatné ID')
        return redirect(url_for('AuthController.login'))
    
    if not user.can_login:
        warning(f'Login attempt by unauthorized user {user.nickname} from {request.remote_addr}')
        flash('Přihlášení je povolené pouze moderátorům')
        return redirect(url_for('AuthController.login'))

    login_user(user)
    info(f'User {user.nickname} (ID: {user.id}) logged in using Oauth (Authorized as {user_id})')
    return redirect(url_for('LeaderboardController.index'))   # TODO: Pamatovat si posledni URL i tady