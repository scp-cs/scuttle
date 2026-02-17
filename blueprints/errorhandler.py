from flask import Blueprint, render_template

ErrorPageController = Blueprint('ErrorHandler', __name__)

@ErrorPageController.app_errorhandler(404)
def e404(error):
    return render_template('errors/error.j2', errno=404, errtext="Not Found", errquote="Není žádná Antimemetická divize.", errlink="http://scp-cs.wikidot.com/your-last-first-day"), 404

@ErrorPageController.app_errorhandler(401)
def e403(error):
    return render_template('errors/error.j2', errno=401, errtext="Unauthorized", errquote="Okamžitě ukončete své spojení a zůstaňte na místě. Najdeme vás.", errlink="http://scp-cs.wikidot.com/scp-6630"), 401

@ErrorPageController.app_errorhandler(500)
def e500(error):
    return render_template('errors/error.j2', errno=500, errtext="Internal Server Error", errquote="[DATA VYMAZÁNA]", errlink="http://scp-cs.wikidot.com/sandrewswann-s-proposal"), 500

@ErrorPageController.app_errorhandler(403)
def e403(error):
    return render_template('errors/error.j2', errno=403, errtext="Forbidden", errquote="Selhání autentizace vyústí v nasazení MTF-Alpha 1 (\"Red Right Hand\"). Přejete si pokračovat?", errlink="http://scp-cs.wikidot.com/tanhony-s-proposal"), 403

@ErrorPageController.app_errorhandler(409)
def e409(error):
    return render_template('errors/error.j2', errno=409, errtext="Conflict", errquote="Nepřesnost. @A8D3.", errlink="http://scp-cs.wikidot.com/scp-7579"), 409