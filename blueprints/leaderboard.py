# External
from flask import Blueprint, request, render_template

# Internal
import db
from db import User

LeaderboardController = Blueprint('LeaderboardController', __name__)

@LeaderboardController.route('/')
def index():
    sort = request.args.get('sort', type=str, default='points')
    page = request.args.get('p', type=int, default=0)
    user_count = User.select().count()
    last_update = db.last_update().strftime("%Y-%m-%d %H:%M:%S")
    data = db.get_frontpage(sort, page)
    return render_template('users.j2', users=data, lastupdate=last_update, user_count=user_count, sort=sort)