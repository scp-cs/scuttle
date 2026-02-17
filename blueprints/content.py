from flask import Blueprint, send_from_directory, request
from os import path, getcwd

ContentController = Blueprint('ContentController', __name__)

PROFILE_DIR = path.join(getcwd(), 'temp', 'avatar')

@ContentController.route('/content/avatar/<int:uid>')
def get_avatar(uid: int):
    if path.exists(path.join('temp', 'avatar', f'{str(uid)}.png')): 
        if request.args.get('s', default='full', type=str) == 'thumb':
            return send_from_directory(PROFILE_DIR, f'{str(uid)}_thumb.png')
        else:
            return send_from_directory(PROFILE_DIR, f'{str(uid)}.png')
    else:
        return send_from_directory('static', 'discord_default.png')