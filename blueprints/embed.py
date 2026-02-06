from http import HTTPStatus
from flask import render_template, Blueprint, abort, request
from enum import StrEnum
from os import getcwd, path, listdir
import json

from db import User, Article

EmbedController = Blueprint('EmbedController', __name__)
EMBED_TEMPLATE_PATH = path.join(getcwd(), 'templates', 'embeds')

class EmbedType(StrEnum):
    TRANSLATOR = "translator"
    WRITER = "writer"
    CORRECTOR = "corrector"

# TODO: Change this to a class-based blueprint
writer_themes_installed = list()
translator_themes_installed = list()

# "record_once" runs the function only when the blueprint is first registered, don't think they could have chosen a worse name
# The record function takes the BlueprintSetupState object but we discard it here as we don't need it
@EmbedController.record_once
def on_blueprint_load(_):
    global writer_themes_installed
    global translator_themes_installed
    # Build a list of themes from files in the templates directory
    writer_themes_installed = [theme.removesuffix('.j2') for theme in listdir(path.join(EMBED_TEMPLATE_PATH, 'writer'))]
    translator_themes_installed = [theme.removesuffix('.j2') for theme in listdir(path.join(EMBED_TEMPLATE_PATH, 'translator'))]

def get_template(template_type: EmbedType, theme: str = "default"):
    if path.exists(path.join(EMBED_TEMPLATE_PATH, template_type, f"{theme}.j2")):
        return f"embeds/{template_type}/{theme}.j2"
    else:
        # Don't abort on invalid theme, just use the default
        return f"embeds/{template_type}/default.j2"

@EmbedController.route('/user/<int:uid>/embed', methods=["GET"])
def user_badge(uid: int):
    embed_type = request.args.get("type", type=str, default=EmbedType.TRANSLATOR)
    if embed_type not in list(EmbedType): abort(HTTPStatus.BAD_REQUEST) # Abort on invalid type
    embed_theme = request.args.get("theme", type=str, default="default")
    user = User.get_or_none(User.id == uid) or abort(HTTPStatus.NOT_FOUND)
    stats = user.stats.first()
    last = user.articles.where(Article.is_original == (embed_type != EmbedType.TRANSLATOR)).order_by(Article.added.desc()).first()
    return render_template(get_template(embed_type, embed_theme), user=user, stats=stats, last=last)

@EmbedController.route('/user/<int:uid>/preview_embed')
def user_badge_preview(uid: int):
    return render_template('embed_preview.j2', uid=uid, writer_themes=json.dumps(writer_themes_installed), translator_themes=json.dumps(translator_themes_installed))