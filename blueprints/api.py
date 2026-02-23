from logging import warning, info, error
from flask import jsonify, request, Blueprint, flash, redirect, url_for, abort
from flask_login import current_user, login_required
from datetime import datetime

from db import Article, User, Frontpage, Correction
from framework.roles import role_badge

ApiController = Blueprint('ApiController', __name__)

PAGE_ITEMS = 15

def result_ok(result = [], extra_data = {}):
    return jsonify({
        'status': 'OK',
        'result': result,
        'hasAuth': current_user.is_authenticated
    } | extra_data)

def result_error(error_message = "", status_code = 400):
    return jsonify({
            'status': 'error',
            'result': [],
            'errorMessage': error_message
        }), status_code

def search_article(query):
    title_param = f'%{query}%'
    link_param = f"%.wikidot.com/%{query}%"
    results = Article.select().where(Article.name ** title_param | Article.link ** link_param).prefetch(User)
    return [{
        'id': a.id,
        'name': a.name,
        'link': a.link,
        'words': a.words,
        'added': a.added,
        'author': {
            'id': a.author.id,
            'name': a.author.display_name or a.author.nickname
        },
        'corrector': {
            'id': a.corrector.id if a.corrector else 0,
            'name': (a.corrector.display_name or a.corrector.nickname) if a.corrector else 'N/A'
        }
    } for a in results]

@ApiController.route('/api/search/article_any')
def search_any_article():
    query = request.args.get('q', None, str)
    if not query:
        return result_error("No query specified", 400)
    
    results = search_article(query)
    return result_ok(results)

@ApiController.route('/api/search/article')
def search_user_article():
    query = request.args.get('q', None, str)
    author = request.args.get('u', None, int)
    if not query or not author:
        return result_error("Parameters missing")
    
    if author == -1:
        return result_ok(search_article(query))
    else:
        title_param = f'%{query}%'
        link_param = f"%.wikidot.com/%{query}%"
        results = Article.select().where((Article.name ** title_param | Article.link ** link_param) & (Article.author == author)).prefetch(User)
        return result_ok([{
                'id': a.id,
                'name': a.name,
                'link': a.link,
                'words': a.words,
                'bonus': a.bonus,
                'added': a.added,
                'corrector': {
                    'id': a.corrector.id if a.corrector else 0,
                    'name': (a.corrector.display_name or a.corrector.nickname) if a.corrector else 'N/A'
                }
            } for a in results])

@ApiController.route('/api/search/user')
def search_user():
    query = request.args.get('q', None, str)
    if not query:
        return result_error("No query specified")
    param = f'%{query}%'
    user = Frontpage.select().join(User).where(Frontpage.user.nickname ** param |
                                                Frontpage.user.wikidot ** param |
                                                Frontpage.user.display_name ** param |
                                                Frontpage.user.discord ** param)
    results = [{'id': u.user.id,
            'nickname': u.user.nickname,
            'discord': u.user.discord,
            'wikidot': u.user.wikidot,
            'displayname': u.user.display_name,
            'tr_count': u.translation_count,
            'cr_count': u.correction_count,
            'orig_count': u.original_count,
            'tr_role_html': role_badge(u.points),
            'points': u.points} for u in user]
    return result_ok(results)

@ApiController.route('/api/user/<int:uid>')
def api_get_user(uid: int):
    user = User.get_or_none(User.id == uid)
    if not user: return result_error("User doesn't exist", 404)

    results = user.to_dict()
    return result_ok(results)

@ApiController.route('/api/user/<int:uid>/articles')
def api_get_articles(uid: int):
    user = User.get_or_none(User.id == uid)
    if not user: return result_error("User doesn't exist", 404)

    page = request.args.get("p", 0, int)
    article_type = request.args.get("t", "translation", str)
    sort = request.args.get("s", "latest", str)

    is_correction = article_type == 'correction'

    match article_type:
        case 'translation':
            select = Article.select().where((Article.is_original == False) & (Article.author == user))
        case 'correction':
            select = Correction.select().where(Correction.corrector == user)
        case 'original':
            select = Article.select().where((Article.is_original == True) & (Article.author == user))
        case _:
            return result_error('Invalid type')

    # Count the articles before we offset and limit
    total = select.count()
    select = select.limit(PAGE_ITEMS).offset(PAGE_ITEMS*page)

    match sort:
        case 'az':
            select = select.order_by(Correction.name.collate("NOCASE") if is_correction else Article.name.collate("NOCASE").asc()).prefetch(User)
        case 'words':
            select = select.order_by(Correction.words.desc() if is_correction else Article.words.desc()).prefetch(User)
        case 'latest':
            select = select.order_by(Correction.timestamp.desc() if is_correction else Article.added.desc()).prefetch(User)
        case _:
            select = select.order_by(Correction.timestamp.desc() if is_correction else Article.added.desc()).prefetch(User)

    return result_ok([r.to_dict() for r in select], {"total": total})

@ApiController.route('/api/user/<int:uid>/assign-correction', methods=['POST'])
@login_required
def assign_correction(uid: int):
    article_id = request.form.get('aid', None, int)
    if not article_id:
        flash('Neplatný článek')
        return result_error('Neplatný článek')
    article = Article.get_or_none(Article.id == article_id)
    if not article:
        flash('Neplatný článek')
        return result_error('Neplatný článek')
    corrector = User.get_or_none(User.id == uid)
    if not corrector:
        flash('Neplatný uživatel')
        return result_error('Neplatný uživatel')
    article.corrected = datetime.now()
    article.corrector = corrector
    article.save()
    info(f"Assigning correction of \"{article.name}\" ({article.id}) to {corrector.nickname} ({corrector.uid})")
    flash('Korekce zapsána')
    return result_ok()

@ApiController.route('/api/article/<int:aid>/remove-correction', methods=["POST"])
@login_required
def remove_correction(aid: int):

    article = Article.get_or_none(Article.id == aid)
    if not article:
        flash('Neplatný článek')
        return result_error('Neplatný článek')

    article.corrected = None
    article.corrector = None
    article.save()
    flash('Korekce odstraněna')
    return result_ok()