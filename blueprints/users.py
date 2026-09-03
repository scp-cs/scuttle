from http import HTTPStatus
from peewee import IntegrityError
from flask import Blueprint, url_for, redirect, session, request, render_template, abort, flash, current_app
from forms import NewUserForm, EditUserForm, PermissionEditForm
from flask_login import current_user, login_required
from db import User, Article
from logging import info, error, warning
from crypto import pw_hash
from tasks import discord_tasks
from secrets import token_urlsafe
from functools import reduce

from extensions import sched, webhook
from framework.accesscontrol import ACLManager, UserPermission

UserController = Blueprint('UserController', __name__)

@UserController.route('/user/new', methods=["GET", "POST"])
@login_required
def add_user():
    if request.method == "GET":
        return render_template('add_user.j2', form=NewUserForm())
    
    form = NewUserForm()
    if not form.validate_and_flash():
        return redirect(url_for('UserController.add_user'))

    user = User()
    user.nickname = form.nickname.data
    user.wikidot = form.wikidot.data
    user.discord = form.discord.data

    if form.can_login.data:
        temp_password = token_urlsafe(8)
        user.password = pw_hash(temp_password)
    try:
        user.save()
    except IntegrityError:
        flash("Uživatel již existuje!")
        return redirect(url_for('UserController.add_user'))

    # Fetch nickname and profile in background
    sched.add_job('Immediate nickname update', lambda: discord_tasks.update_nicknames_task(override_users=[user]))
    sched.add_job('Immediate profile update', lambda: discord_tasks.download_avatars_task(override_users=[user]))
    
    if form.can_login.data:
        session['tpw'] = temp_password
        session['tmp_uid'] = user.get_id()
        info(f"Administrator account created for {form.nickname.data} with ID {user.get_id()} by {current_user.nickname} (ID: {current_user.get_id()})")
    else:
        info(f"User account created for {form.nickname.data} with ID {user.get_id()} by {current_user.nickname} (ID: {current_user.get_id()})")
    
    return redirect(url_for('AuthController.temp_pw') if form.can_login.data else url_for('UserController.user', uid=user.get_id()))

@UserController.route('/user/<int:uid>/edit', methods=["GET", "POST"])
@login_required
def edit_user(uid: int):
    user = User.get_or_none(User.id == uid) or abort(HTTPStatus.NOT_FOUND)

    if request.method == "GET":
        fdata = {'nickname': user.nickname, 'wikidot': user.wikidot, 'discord': user.discord, 'login': int(user.password is not None)}
        return render_template('edit_user.j2', form=EditUserForm(data=fdata), user=user)
    
    form = EditUserForm()
    if not form.validate_and_flash():
        return redirect(url_for('UserController.edit_user', uid=uid))

    user.nickname = form.nickname.data
    user.wikidot = form.wikidot.data
    user.discord = form.discord.data
    user.save()

    info(f"User {user.nickname} (ID: {uid}) edited by {current_user.nickname} (ID: {current_user.get_id()})")
    return redirect(url_for('UserController.user', uid=uid))

@UserController.route('/user/<int:uid>')
def user(uid: int):
    sort = request.args.get('sort', 'latest', str)
    user = User.get_or_none(User.id == uid) or abort(HTTPStatus.NOT_FOUND)
    corrections = list(user.corrections)
    # TODO: Extract constant
    translations = list(user.articles.where(Article.is_original == False).order_by(Article.added.desc()).limit(15).prefetch(User))
    originals = list(user.articles.where(Article.is_original == True).prefetch(User))
    perms_strings = [(p.name, ACLManager.get_permission_color_class(p)) 
                        for p in ACLManager._expand_permissions(UserPermission(user.permissions))]
    if len(perms_strings) == 0:
        perms_strings = [('ŽÁDNÁ', 'bg-white/5 border-white/20')]
    return render_template('user.j2',
                           user=user,
                           stats=user.stats.first(),
                           translations=translations,
                           corrections=corrections,
                           originals=originals,
                           sort=sort,
                           perms=perms_strings)

# TODO: Make this and some other destructive routes POST-only
# TODO: Maybe just hide users instead of deleting them as to not fuck up DB integrity
@UserController.route('/user/<int:uid>/delete', methods=["POST", "GET"])
@login_required
def delete_user(uid: int):
    user = User.get_or_none(User.id == uid) or abort(HTTPStatus.NOT_FOUND)
    name = user.nickname
    user.delete_instance()
    info(f"User {name} deleted by {current_user.nickname} (ID: {current_user.get_id()})")
    flash(f'Uživatel {name} smazán')
    
    return redirect(url_for('LeaderboardController.index'))

@UserController.route('/user/<int:uid>/admin/grant')
@login_required
def grant_admin_perms(uid: int):
    user = User.get_or_none(User.id == uid) or abort(HTTPStatus.NOT_FOUND)
    password = user.password
    if password is not None:
        error(f"Granting administrator permissions to an administrator {user.nickname} (ID: {uid})")
        abort(HTTPStatus.CONFLICT)

    if user.discord == current_app.config['DISCORD_ROLEMASTER_ID']:
        error("Cannot grant admin permissions to master admin")
        abort(HTTPStatus.FORBIDDEN)

    temp_password = token_urlsafe(8)
    user.password = pw_hash(temp_password)
    user.temp_pw = True
    user.save()

    session['tpw'] = temp_password
    session['tmp_uid'] = user.get_id()

    info(f"Administrator permissions granted to {user.nickname} (ID: {uid}) by {current_user.nickname} (ID: {current_user.get_id()})")
    flash(f'Uživatel {user.nickname} je nyní administrátor')
    webhook.send_text(f"Uživateli {user.nickname} byla udělena administrátorská práva")
    
    return redirect(url_for('AuthController.temp_pw'))

@UserController.route('/user/<int:uid>/admin/revoke')
@login_required
def revoke_admin_perms(uid: int):
    user = User.get_or_none(User.id == uid) or abort(HTTPStatus.NOT_FOUND)
    password = user.password
    if password is None:
        error(f"Removing administrator permissions from a non-administrator {user.nickname} (ID: {uid})")
        abort(HTTPStatus.CONFLICT)

    if user.discord == str(current_app.config['DISCORD_ROLEMASTER_ID']):
        error(f"Attempting to remove administrator permissions from master admin (by {current_user.nickname} ID: {current_user.get_id()})")
        flash(f"Hlavnímu administrátorovi nelze odebrat práva")
        abort(HTTPStatus.FORBIDDEN)

    user.temp_pw = 1
    user.password = None
    user.save()

    info(f"Administrator permissions revoked from {user.nickname} (ID: {uid}) by {current_user.nickname} (ID: {current_user.get_id()})")
    flash(f'Uživatel {user.nickname} už není administrátor')
    webhook.send_text(f"Uživateli {user.nickname} byla odebrána administrátorská práva")
    
    return redirect(url_for('UserController.user', uid=uid))

@UserController.route('/user/<int:uid>/permissions', methods=["GET", "POST"])
@login_required
def edit_permissions(uid: int):
    user = User.get_or_none(User.id == uid) or abort(HTTPStatus.NOT_FOUND)
    if user.permissions & UserPermission.MASTER_ADMIN:
        flash("Oprávnění tohoto uživatele nelze upravovat")
        return redirect(url_for('UserController.user', uid=uid))
    perms = ACLManager._expand_permissions(UserPermission(user.permissions))
    form = PermissionEditForm()
    if request.method == "GET":
        form.perms.data = list(perms)
        return render_template('auth/permissions.j2', form=form)

    if not form.validate_and_flash():
        return redirect(url_for('UserController.edit_permissions', uid=uid))

    new_perms = ACLManager._expand_permissions(UserPermission(reduce(lambda x, y: x | y, form.perms.data)))
    perm_diff = perms ^ new_perms

    if not perm_diff:
        flash("Nebyly provedeny žádné změny")
        return redirect(url_for('UserController.user', uid=uid))

    current_user_perms = ACLManager._expand_permissions(UserPermission(current_user.permissions))

    if not ACLManager.can_alter_perms(current_user_perms, perm_diff):
        warning(f"Permission change {user.permissions} => {new_perms} rejected. Source: {current_user.nickname} (ID: {current_user.id}), Target: {user.nickname} (ID: {user.id})")
        flash("Na provedení této operace nemáte oprávnění")
        return redirect(url_for('UserController.user', uid=uid))

    user.permissions = new_perms
    user.save()
    flash("Oprávnění aktualizována")
    info(f"Permission change {user.permissions} => {new_perms} accepted. Source: {current_user.nickname} (ID: {current_user.id}), Target: {user.nickname} (ID: {user.id})")
    return redirect(url_for('UserController.user', uid=uid))