from flask import Blueprint, send_from_directory, request
from os import path, getcwd

ContentController = Blueprint('ContentController', __name__)

PROFILE_DIR = path.join(getcwd(), 'temp', 'avatar')

# This really should be sent by the webserver too but unnnghhh hard
# (also I cannot imagine any scenario where an instance of this app gets more than a couple dozen of users every day)
@ContentController.route('/content/avatar/<int:uid>')
def get_avatar(uid: int):
    if path.exists(path.join('temp', 'avatar', f'{str(uid)}.png')): 
        if request.args.get('s', default='full', type=str) == 'thumb':
            return send_from_directory(PROFILE_DIR, f'{str(uid)}_thumb.png')
        else:
            return send_from_directory(PROFILE_DIR, f'{str(uid)}.png')
    else:
        return send_from_directory('static', 'discord_default.png')

# Just a quick hack, the reverse proxy should really be configured to send this
# through a file server without Flask ever touching the request
@ContentController.route('/robots.txt')
def robots_txt():
    return send_from_directory('static', 'robots.txt')