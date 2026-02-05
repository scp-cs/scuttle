import datetime
from peewee import *
from logging import debug

database = SqliteDatabase("data/scp.db")

PAGE_ITEMS = 15

# Creates the views that peewee doesn't support by executing raw SQL
def create_views(database: SqliteDatabase):
    debug("Creating database views")

    # TODO: This is so fucking horrible like what am I even looking at whz did I write this

    database.execute_sql("CREATE VIEW IF NOT EXISTS Frontpage AS\
    SELECT User.id AS id, User.nickname AS nickname, User.discord AS discord, User.wikidot AS wikidot, User.display_name as display, \
        SUM(CASE WHEN Article.is_original=FALSE THEN 1 ELSE 0 END) AS translation_count, \
        (SUM(CASE WHEN Article.is_original=FALSE THEN Article.words ELSE 0 END)/1000.0)+TOTAL(Article.bonus) AS points,\
        (SELECT COUNT(article_id) FROM Correction WHERE Corrector=User.id) AS correction_count,\
        SUM(CASE WHEN Article.is_original=TRUE THEN 1 ELSE 0 END) AS original_count\
            FROM user\
                LEFT JOIN Article \
                    ON User.id = Article.idauthor\
            GROUP BY User.id;")
    
    database.execute_sql("CREATE VIEW IF NOT EXISTS Series AS \
        SELECT (SUBSTR(name, 5)/1000)+1 AS series, COUNT(id) AS articles, SUM(words) AS words \
            FROM Article \
            WHERE (name \
                LIKE 'SCP-___' OR name LIKE 'SCP-____') AND is_original=FALSE \
            GROUP BY SERIES\
        UNION\
        SELECT 999 AS series, COUNT(id) AS articles, SUM(words) AS words\
            FROM Article\
            WHERE name\
                NOT LIKE 'SCP-___' AND name NOT LIKE 'SCP-____' AND is_original=FALSE;")
    
    database.execute_sql("CREATE VIEW IF NOT EXISTS Statistics AS\
        SELECT SUM(t.words) AS total_words, COUNT(t.id) AS total_articles, (SELECT COUNT(id) FROM user) AS total_users\
            FROM Article AS t WHERE t.is_original=FALSE;")
    
    database.execute_sql("CREATE VIEW IF NOT EXISTS Correction AS\
        SELECT id as article_id, idauthor AS author, idcorrector AS corrector, corrected AS timestamp, words, name\
            FROM Article WHERE idcorrector IS NOT NULL;")

class BaseModel(Model):
    class Meta:
        database = database

class ViewModel(BaseModel):
    def save(self):
        raise RuntimeError("Attempted to insert into an SQL View")
    
    class Meta:
        primary_key = False

# type: ignore
class User(BaseModel):
    id = AutoField()
    discord = TextField(null=True)
    display_name = TextField(null=True)
    nickname = TextField(unique=True)
    password = BlobField(null=True)
    temp_pw = BooleanField(default=True, null=True)
    wikidot = TextField(unique=True)
    avatar_hash = TextField(default=True, null=True)

    @property
    def can_login(self) -> bool:
        return self.password != None
    
    # Flask-Login stuff
    is_anonymous = False
    is_active = True
    
    @property
    def is_authenticated(self) -> bool:
        return len(self.password) > 0

    def to_dict(self) -> dict:
        return {
        'id': self.id,
        'nickname': self.nickname,
        'wikidot': self.wikidot,
        'discord': self.discord,
        'displayName': self.display_name
    }

    class Meta:
        table_name = 'User'

class Article(BaseModel):
    id = AutoField()
    added = DateTimeField(default=datetime.datetime.now)
    bonus = IntegerField()
    corrected = DateTimeField(null=True)
    author = ForeignKeyField(column_name='idauthor', field='id', model=User, backref='articles')
    corrector = ForeignKeyField(backref='corrections', column_name='idcorrector', field='id', model=User, null=True)
    is_original = BooleanField(default=False)
    link = TextField(null=True)
    name = TextField()
    words = IntegerField()

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "words": self.words,
            "bonus": self.bonus,
            "added": self.added,
            "author": self.author.to_dict(),
            "corrector": self.corrector.to_dict() if self.corrector else None,
            "corrected": self.corrected,
            "link": self.link
            }

    class Meta:
        table_name = 'Article'

class Backup(BaseModel):
    id = AutoField()
    articles = IntegerField()
    date = DateTimeField(default=datetime.datetime.now)
    fingerprint = BlobField()
    author = ForeignKeyField(column_name='idauthor', field='id', model=User, backref='backups')
    sha1 = BlobField()

    class Meta:
        table_name = 'Backup'

class Note(BaseModel):
    id = AutoField()
    content = TextField()
    author = ForeignKeyField(column_name='idauthor', field='id', model=User, backref='created_notes')
    title = TextField()
    related_article = ForeignKeyField(column_name='related_article', field='id', model=Article, backref="notes", null=True)
    related_user = ForeignKeyField(column_name='related_user', field='id', model=User, backref="notes", null=True)
    related_backup = ForeignKeyField(column_name='related_backup', field='id', model=Backup, backref="notes", null=True)

    class Meta:
        table_name = 'Note'

class UserType(BaseModel):
    id = AutoField()
    name = TextField(unique=True)

    class Meta:
        table_name = 'UserType'

class UserHasType(BaseModel):
    user_type = ForeignKeyField(column_name='idtype', field='id', model=UserType, backref='users')
    user = ForeignKeyField(column_name='iduser', field='id', model=User, backref='types')

    class Meta:
        table_name = 'UserHasType'

class Backup(BaseModel):
    id = AutoField()
    date = TimestampField()
    article_count = IntegerField(null=True)
    author = ForeignKeyField(User, backref="author", null=True)
    fingerprint = CharField(16, null=True)
    sha1 = CharField(48, null=True, unique=True)
    is_finished = BooleanField(default=False)

class Wiki(BaseModel):
    id = AutoField()
    url = TextField()
    name = TextField()
    total_artices = IntegerField(null=True)
    is_active = BooleanField(default=True)

class BackupHasWiki(BaseModel):
    wiki = ForeignKeyField(Wiki)
    backup = ForeignKeyField(Backup)

class WikiCommaConfig(BaseModel):
    id = AutoField()
    http_proxy = TextField(null=True)
    socks_proxy = TextField(null=True)
    delay = IntegerField(null=True)
    ratelimit_size = IntegerField(null=True)
    ratelimit_refill = IntegerField(null=True)
    blacklist = TextField(null=True)

class Series(ViewModel):
    series = IntegerField()
    articles = IntegerField()
    words = IntegerField()

    class Meta:
        table_name = 'Series'

class Statistics(ViewModel):
    total_words = IntegerField()
    total_articles = IntegerField()
    total_users = IntegerField()

    class Meta:
        table_name = 'Statistics'

class Correction(ViewModel):
    article = ForeignKeyField(Article, field='id', column_name='article_id', backref='correction')
    author = ForeignKeyField(User, field='id', column_name='author')
    corrector = ForeignKeyField(User, field='id', backref='corrections', column_name='corrector')
    timestamp = DateTimeField()
    words = IntegerField()
    name = TextField()

    def to_dict(self):
        return {
            'article': self.article.to_dict(),
            'author': self.author.to_dict(),
            'corrector': self.corrector.to_dict(),
            'timestamp': self.timestamp,
            'words': self.words
        }

class Frontpage(ViewModel):
    user = ForeignKeyField(User, field='id', column_name='id', backref='stats')
    translation_count = IntegerField()
    points = FloatField()
    correction_count = IntegerField()
    original_count = IntegerField()

models = [User, Article, Backup, Note, UserType, UserHasType, Backup, Wiki, WikiCommaConfig, BackupHasWiki]

def last_update() -> datetime.datetime:
    return Article.select(fn.MAX(Article.added)).scalar() or datetime.datetime(year=1990, month=1, day=1)

def get_frontpage(sort: str, page: int):
    entries = Frontpage.select().join(User).limit(PAGE_ITEMS).offset(PAGE_ITEMS*page)
    match sort:
        case 'az':
            result = entries.order_by(User.nickname.collate("NOCASE").asc()).prefetch(User)
        case 'points':
            result = entries.order_by(Frontpage.points.desc()).prefetch(User)
        case 'count':
            result = entries.order_by(Frontpage.translation_count.desc()).prefetch(User)
        case 'corrections':
            result = entries.order_by(Frontpage.correction_count.desc()).prefetch(User)
        case 'originals':
            result = entries.order_by(Frontpage.original_count.desc()).prefetch(User)
        case _:
            result = entries.order_by(Frontpage.points.desc()).prefetch(User)
    return result
