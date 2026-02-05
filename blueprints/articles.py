# Builtins
from datetime import datetime
from http import HTTPStatus
from logging import info, error

# External
from flask import Blueprint, flash, redirect, request, render_template, abort, url_for, session, current_app
from flask_login import current_user, login_required

# Internal
from forms import NewArticleForm, EditArticleForm, AssignCorrectionForm
from framework.roles import get_role
from extensions import rss, webhook
from db import User, Article

ArticleController = Blueprint('ArticleController', __name__)

def check_role_and_notify(uid, point_amount):
    promoted_user = User.get_or_none(User.id == uid)
    if not promoted_user:
        error(f"How the fuck does this even happen? (Sending promote notify for a nonexistent user {uid})")
        return
    current_points = promoted_user.stats.first().points
    current_role = get_role(current_points)
    next_role = get_role(current_points + point_amount)
    if current_role != next_role:
        if promoted_user.discord:
            webhook.send_text(f'Uživatel {promoted_user.nickname} (<@{promoted_user.discord}>) dosáhl hranice pro roli {next_role["name"]}!')

@ArticleController.route('/article/<int:aid>/delete', methods=["POST"])
@login_required
def delete_article(aid: int):
    article = Article.get_or_none(Article.id == aid) or abort(HTTPStatus.NOT_FOUND)
    article.delete_instance()
    info(f"Article {article.name} deleted by {current_user.nickname} (ID: {current_user.get_id()})")
    flash(f'Článek {article.name} smazán')
    return "OK"

@ArticleController.route('/user/<int:uid>/new_article', methods=["GET", "POST"])
@login_required
def add_article(uid):

    if request.method == "GET":
        form = NewArticleForm()
        if request.args.get('rss', None):
            form.title.data = request.args.get('t')
            form.link.data = request.args.get('l')
            session['NEW_FROM_RSS'] = True
            session['RSS_UUID'] = request.args.get('u')
        return render_template('add_translation.j2', form=form, user=User.get_by_id(uid))
    
    form = NewArticleForm()
    if not form.validate_and_flash():
        return redirect(url_for('ArticleController.add_article', uid=uid))

    title = form.title.data.upper() if form.title.data.lower().startswith('scp') else form.title.data # Capitalize SCP
    is_original = bool(request.args.get('original', False))

    if Article.select().where(Article.name == title).exists():
        flash(f'Překlad již existuje! (od uživatele {Article.get(Article.name == title).author.nickname})')
        return redirect(url_for('ArticleController.add_article', uid=uid))
    
    if current_app.config['WEBHOOK_ENABLE'] and not is_original:
        check_role_and_notify(uid, form.words.data / 1000 + form.bonus.data)

    article = Article()
    article.name = title
    article.words = form.words.data
    article.bonus = form.bonus.data
    article.author = User.get_by_id(uid)
    article.link = form.link.data
    article.is_original = is_original

    article.save()
    
    if 'NEW_FROM_RSS' in session:
        del session['NEW_FROM_RSS']
        rss.remove_update(session['RSS_UUID'])
        del session['RSS_UUID']
        info(f"Article {article.name} (ID: {article.id}) added from RSS by {current_user.nickname} (ID: {current_user.get_id()})")
    else:
        info(f"Article {article.name} (ID: {article.id}) added by {current_user.nickname} (ID: {current_user.get_id()})")
    
    return redirect(url_for('UserController.user', uid=uid))

@ArticleController.route('/article/<int:aid>/edit', methods=["GET", "POST"])
@login_required
def edit_article(aid: int):

    article = Article.get_or_none(Article.id == aid) or abort(HTTPStatus.NOT_FOUND)        

    if request.method == "GET":
        fdata = {'title': article.name, 'words': article.words, 'bonus': article.bonus, 'link': article.link, 'translator': article.author.nickname}
        return render_template('edit_article.j2', form=EditArticleForm(data=fdata))
    
    form = EditArticleForm()
    if not form.validate_and_flash():
        return redirect(url_for('UserController.user', uid=article.author.get_id()))

    point_diff = (form.words.data - article.words)/1000 + (form.bonus.data - article.bonus)
    if point_diff > 0:
        check_role_and_notify(article.author.id, point_diff)

    title = form.title.data.upper() if form.title.data.lower().startswith('scp') else form.title.data

    article.name = title
    article.words = form.words.data
    article.link = form.link.data
    article.bonus = form.bonus.data
    article.save()

    info(f"Article {article.name} (ID: {aid}) edited by {current_user.nickname} (ID: {current_user.get_id()})")

    return redirect(url_for('UserController.user', uid=article.author.get_id()))

# TODO: No idea if this isn't broken now
@ArticleController.route('/article/assign-correction', methods=["POST"])
@login_required
def assign_correction():
    form = AssignCorrectionForm()
    back_to_changes = redirect(url_for('RssPageController.rss_changes'))
    article = Article.get_or_none(Article.id == form.article_id.data)
    if not article:
        return back_to_changes

    corrector = User.get_or_none(User.id == form.corrector_id.data)
    if not corrector:
        flash('Nastala chyba, zkuste to znovu')
        return back_to_changes

    article.link = form.link.data
    # TODO: Duplicate titles allowed on wiki but not in db, might mess shit up one day
    article.name = form.title.data
    article.corrector = corrector
    article.corrected = datetime.now()
    article.save()

    rss.remove_update(form.guid.data)
    flash('Článek aktualizován')
    return back_to_changes

