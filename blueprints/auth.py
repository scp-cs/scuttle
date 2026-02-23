# Builtins
from logging import info, error
from os import getcwd, path

# External
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from forms import LoginForm, PasswordChangeForm
from flask_login import login_user, login_required, logout_user, current_user

# Internal
from crypto import pw_check, pw_hash
from db import User

AuthController = Blueprint('AuthController', __name__, template_folder=path.join(getcwd(), 'templates', 'auth'))

@AuthController.route('/login', methods=["GET", "POST"])
def login():

    if request.method == "GET":
        # Saves the last URL, but prevents the user from staying on the logging page
        # if the first login attempt fails
        if request.referrer and not request.referrer.endswith('/login'):
            session['login_next'] = request.referrer
        return render_template('login.j2', form=LoginForm())

    form = LoginForm()
    if not form.validate_and_flash():
        return redirect(url_for('AuthController.login'))

    user = User.get_or_none(User.nickname == form.username.data)
    if user is None or not pw_check(form.password.data, user.password):
        flash('Nesprávné uživatelské jméno nebo heslo')
        return redirect(url_for('AuthController.login'))

    if user.temp_pw:
        session['PRE_LOGIN_UID'] = user.id
        return redirect(url_for('AuthController.pw_change'))
    login_user(user)
    referrer = session.get('login_next', None)

    del session['login_next']
    return redirect(referrer or url_for('LeaderboardController.index'))


@AuthController.route('/user/logout')
@login_required
def logout():
    logout_user()
    flash('Uživatel odhlášen')
    return redirect(request.referrer or url_for('LeaderboardController.index'))

@AuthController.route('/user/pw_change', methods=["GET", "POST"])
def pw_change():

    if ('PRE_LOGIN_UID' not in session) and not current_user.is_authenticated:
        return redirect(url_for('LeaderboardController.index'))

    if request.method == "GET":
        return render_template('pw_change.j2', form=PasswordChangeForm())
    
    form = PasswordChangeForm()

    if not form.validate_and_flash():
        return redirect(url_for('AuthController.pw_change'))

    if not current_user.is_authenticated:
        user = User.get_or_none(User.id == session['PRE_LOGIN_UID'])
    else: 
        user = current_user

    if user is None:
        error("Invalid auth state (Temporary PW change in progress but user not found)")
        return redirect(url_for('LeaderboardController.index'))
    user.password = pw_hash(form.pw.data)
    user.temp_pw = False
    user.save()

    if not current_user.is_authenticated:
        login_user(user)
    if 'PRE_LOGIN_UID' in session:
        del session['PRE_LOGIN_UID']
    if not current_user.is_authenticated:
        info(f"Permanent password created for {user.nickname} (ID: {user.id})")
    else:
        flash("Heslo změněno")
        info(f"Password changed for user {user.nickname} (ID: {user.id})")
    return redirect(url_for('LeaderboardController.index'))

@AuthController.route('/user/new/pw')
def temp_pw():

    if 'tpw' not in session:
        return redirect(url_for('AuthController.login'))

    user = User.get_or_none(User.id == session['tmp_uid'])
    if user is None:
        error("Invalid auth state (Created administrator with invalid ID)")
        return redirect(url_for('LeaderboardController.index'))

    tpw = session['tpw']
    del session['tpw']
    del session['tmp_uid']
    return render_template('temp_pw.j2', user=user, tpw=tpw)
