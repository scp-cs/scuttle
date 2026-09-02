from typing import Any
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, IntegerField, BooleanField, ValidationError, HiddenField
from wtforms.validators import EqualTo, Length, url, NumberRange, InputRequired
from flask import flash

class FlaskFormEx(FlaskForm):
    def validate_and_flash(self) -> bool:
        """
        Validates the form and flashes all validation errors.
        Returns the result of validate_on_submit
        """
        if not self.validate_on_submit():
            for e in self.errors.values():
                flash(e[0], category="error")
            return False
        return True

# Can be used like a normal WTForms validator
class DiscordID():
    def __call__(self, form, field) -> Any:
        if len(field.data) not in [18, 19]:
            raise ValidationError('Discord ID musí mít 18 nebo 19 znaků')
        try:
            a = int(field.data)
        except ValueError:
            raise ValidationError('Discord ID může obsahovat pouze číslice')

class LoginForm(FlaskFormEx):
    username = StringField('Uživatelské Jméno', validators=[InputRequired()])
    password = PasswordField('Heslo', validators=[InputRequired()])
    submit = SubmitField('Přihlásit')

class PasswordChangeForm(FlaskFormEx):
    password = PasswordField('Heslo', validators=[EqualTo('password_confirm', "Hesla se musí shodovat"), Length(6, message="Heslo musí mít 6 - 64 znaků")])
    password_confirm = PasswordField('Potvrdit heslo')
    submit = SubmitField('Změnit heslo')

class NewArticleForm(FlaskFormEx):
    title = StringField('Název', validators=[InputRequired(message="Zadejte název článku")])
    translator = StringField('Překladatel')
    words = IntegerField('Počet slov', validators=[InputRequired(message="Zadejte počet slov")])
    bonus = IntegerField('Bonusové body', default=0)
    link = StringField('Odkaz')
    excluded = BooleanField('Vyloučit z počítání bodů', default=False)
    submit = SubmitField('Odeslat')

class EditArticleForm(NewArticleForm):
    pass

class NewUserForm(FlaskFormEx):
    nickname = StringField('Přezdívka', validators=[InputRequired()])
    wikidot = StringField('Wikidot ID', validators=[InputRequired()])
    discord = StringField('Discord ID', validators=[DiscordID()])
    can_login = BooleanField('Administrátor')
    permissions = IntegerField('Oprávnění')
    submit = SubmitField('Přidat')

class EditUserForm(NewUserForm):
    nickname = StringField('Přezdívka', validators=[InputRequired()])
    wikidot = StringField('Wikidot ID', validators=[InputRequired()])
    discord = StringField('Discord ID', validators=[DiscordID()])
    submit = SubmitField('Uložit')

class PasswordChangeForm(FlaskFormEx):
    pw = PasswordField('Heslo', validators=[InputRequired()])
    pw_confirm = PasswordField('Potvrzení hesla', validators=[InputRequired(), EqualTo('pw', message="Hesla se musí shodovat")])
    submit = SubmitField('Potvrdit')

class AssignCorrectionForm(FlaskFormEx):
    article_id = HiddenField('id', validators=[NumberRange(0, message="ID musí být číslo")])
    corrector_id = HiddenField('corrector')
    guid = HiddenField('guid')
    link = HiddenField('link')
    title = HiddenField('title')
    submit = SubmitField('Přiřadit')