# Builtins
from typing import List
import re
from logging import debug, info, error, warning, debug
from datetime import datetime, timedelta
from dataclasses import dataclass
from uuid import uuid4, UUID
from flask import Flask
from enum import IntEnum
from typing import Optional
from collections import deque
from urllib.parse import urlparse, urlunparse

# Internal
from db import User, Article, last_update
import connectors.wikidotsite as wikidotsite
from utils import config_has_key

# External
import requests
import feedparser
from peewee import fn

# Extract the actual title from the feed's title element
r_title = re.compile(r"\"(.+)\".+", re.UNICODE)

# Extract the author's wikidot username from the HTML formatted description
r_user = re.compile(r'href="http:\/\/www\.wikidot\.com\/user:info\/(.+?)"', re.UNICODE)

# TODO: Move this to config, possibly create separate config for RSS feeds
NEW_PAGE = 'nová stránka'   # This text in the title indicates a new page
PAGE_RENAME = 'přesunout/přejmenovat stránku' # This text in the title indicates a page move
CORRECTION_COMPLETE = 'Odstraněné štítky: korekce'
IGNORE_BRANCH_TAG = '-cs' # Ignore new pages that start with this tag, doesn't work for tales but I don't really care
TIMEZONE_UTC_OFFSET = timedelta(hours=2)

class RSSUpdateType(IntEnum):
    RSS_NEWPAGE = 0
    RSS_RENAME = 1
    RSS_SOURCECHANGE = 2
    RSS_DELETE = 3
    RSS_CORRECTION = 4
    RSS_UNKNOWN = 5

@dataclass
class RSSUpdate:
    timestamp: datetime
    link: str
    title: str
    author: User
    uuid: UUID
    update_type: RSSUpdateType

class RSSMonitor:
    
    def __init__(self, links: List[str] = []):
        self.__links = links
        self.__updates = list() #TODO: Make this a dict indexed by the GUID
        self.__finished_guids = deque(maxlen=255)
        # Maps domains to the names of wikis translated from
        self.__source_wiki_map = {}
        self.__save_snapshots = False

    def init_app(self, app: Flask) -> None:
        if 'MONITORED_WIKIS' not in app.config:
            warning('RSSMonitor has no endpoints!')
            return
        self.__save_snapshots = config_has_key(app.config, "BACKUP.save_snapshots", check_true=True)
        for wiki in app.config['MONITORED_WIKIS']:
            self.__links.append(wiki['feed_url'])
            if self.__save_snapshots and 'source_wiki' in wiki:
                wiki_url_base = urlparse(wiki['feed_url']).netloc
                self.__source_wiki_map[wiki_url_base] = wiki['source_wiki']
        if self.__save_snapshots:
            debug(f"Mapped source wikis: {self.__source_wiki_map}")
        self.__webhook = app.config['webhook']

        info(f'Loaded {len(self.__links)} RSSMonitor endpoints from config')

    @staticmethod
    def get_rss_update_type(update: dict) -> RSSUpdateType:
        update_title = update['title']
        if NEW_PAGE in update_title:
            return RSSUpdateType.RSS_NEWPAGE
        elif PAGE_RENAME in update_title:
            return RSSUpdateType.RSS_RENAME
        elif CORRECTION_COMPLETE in update['description']:
            return RSSUpdateType.RSS_CORRECTION
        else:
            return RSSUpdateType.RSS_UNKNOWN
    
    # Wikidot always converts the username to lowercase and replaces spaces/underscores with dashes for the url slug
    # Makes finding users kinda a pain in the ass
    def get_rss_update_author(self, update: dict) -> Optional[User]:
        update_description = update['description']
        username = r_user.search(update_description).group(1).lower()
        debug(f"Extracted username \"{username}\"")
        user = User.get_or_none(fn.LOWER(User.wikidot) == username) # Spaces and underscores get replaced with dashes in the URL, there's no way around this unfortunately
        if not user: #! This is going to break if a user has two of these symbols in their name
            username = username.replace('-', ' ')
            user = User.get_or_none(fn.LOWER(User.wikidot) == username)
        if not user:
            username = username.replace(' ', '_')
            user = User.get_or_none(fn.LOWER(User.wikidot) == username)
        if not user:
            debug(f"Failed to find user \"{username}\"")
        return user
    
    # Try both http and https scheme, Wikidot is the only site in existence
    # that isn't all HTTPS in 2025, so they tend to get mixed up
    # Using urllib functions for this would be good practice but fuck it tbh
    @staticmethod
    def find_link(link: str) -> Optional[Article]:
        article = Article.get_or_none(Article.link == link)
        if not article:
            if link.startswith("https"):
                link = link.replace("https", "http", 1)
            else:
                link = link.replace("http", "https", 1)
            article = Article.get_or_none(Article.link == link)
        return article
        
    @staticmethod
    def get_rss_update_title(update: dict) -> str:
        return r_title.search(update['title']).group(1)

    @staticmethod
    def get_rss_update_timestamp(update: dict) -> datetime:
        return datetime.strptime(update['published'], "%a, %d %b %Y %H:%M:%S +%f")
    
    @staticmethod
    def get_update_revision(update: dict) -> int:
        return update['guid'].split('#')[1].removeprefix("revision-")

    def _process_new_page(self, update) -> bool:
        timestamp = RSSMonitor.get_rss_update_timestamp(update)
        title = RSSMonitor.get_rss_update_title(update)
        author = self.get_rss_update_author(update)
        revision = RSSMonitor.get_update_revision(update)
        link = update['link']

        if self.__save_snapshots:
            source_wiki = urlparse(link).netloc
            if wikidotsite.source_page_exists(link, self.__source_wiki_map[source_wiki]):
                wikidotsite.snapshot_original(link, revision_id=revision, source_wiki_name=self.__source_wiki_map[source_wiki])

        if not author:
            info(f'Ignoring {title} in RSS feed (couldn\'t match wikidot username {author} to a user)')
            return False
        debug(f'Check {title} with ts {timestamp}, last db update was {last_update()}')
        
        if timestamp+TIMEZONE_UTC_OFFSET > last_update():
            if RSSMonitor.find_link(link):
                info(f'Ignoring {title} in RSS feed (added manually)')
                return False
            self.__updates.append(RSSUpdate(timestamp+TIMEZONE_UTC_OFFSET, link, title, author, uuid4(), RSSUpdateType.RSS_NEWPAGE))
            return True
        return False

    def _process_correction(self, update) -> bool:
        real_title = update["title"].split("\"")[1]
        author = self.get_rss_update_author(update)
        timestamp = RSSMonitor.get_rss_update_timestamp(update)
        if not author:
            debug(f"RSS Assign failed - RSS author is {author}, RSS title is {real_title}")
            self.__webhook.send_text(f'Korekci pro {real_title} nelze přiřadit k autorovi. Uživatel neexistuje.')
            warning(f"Correction for {real_title} cannot be assigned to a user")
        else:
            translation = RSSMonitor.find_link(update['link'])
            if not translation:
                self.__updates.append(RSSUpdate(timestamp+TIMEZONE_UTC_OFFSET, update['link'], real_title, author, uuid4(), RSSUpdateType.RSS_CORRECTION))
                warning(f"Correction for {real_title} by {author.nickname} cannot be assigned to an article")
            else:
                translation.corrector = author
                translation.corrected = datetime.now()
                translation.save()
                info(f'Assigned correction by {author.nickname} to {translation.name}')

    def _process_update(self, update) -> bool:
        if update['guid'] in self.__finished_guids:
            debug(f"Skip GUID {update['guid']}")
            return False

        if update['guid'] not in self.__finished_guids:
            debug(f"Add GUID {update['guid']}")
            self.__finished_guids.append(update['guid'])
        update_type = RSSMonitor.get_rss_update_type(update)
        match update_type:
            case RSSUpdateType.RSS_NEWPAGE:
                if self._process_new_page(update):
                    return True
            case RSSUpdateType.RSS_CORRECTION:
                self._process_correction(update)

        return False
        
    def check(self):
        info(f'Fetching {len(self.__links)} RSS feeds')
        if not self.__links:
            return
        
        new_count = 0
        for link in self.__links:
            try:
                feed = feedparser.parse(link).get('entries')
            except Exception as e:
                error(f"RSS Update failed for feed {link} ({e})")
                
            for update in feed:
                if self._process_update(update): new_count += 1

        info(f'Got {new_count or "no"} new pages from RSS feeds')

    @property
    def updates(self) -> List[RSSUpdate]:
        return self.__updates
    
    @property
    def update_count(self) -> int:
        return len(self.__updates)
    
    @property
    def has_links(self) -> bool:
        return len(self.__links) > 0
    
    def remove_update(self, uuid: str) -> Optional[str]:
        for update in self.__updates:
            if str(update.uuid).lower() == uuid.lower():
                debug(f'{update.link} mark finished (remove)')
                self.__updates.remove(update)
                return update.title
        return None

    def flush_updates(self) -> None:
        self.__updates.clear()