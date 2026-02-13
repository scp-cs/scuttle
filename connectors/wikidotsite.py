# Builtins
from typing import Optional
from os import path, PathLike, getcwd
from logging import info, error, warning, debug

# Internal
from db import Article
from constants import USER_AGENT

# External
from flask import current_app
from urllib import parse
import wikidot
import requests

def source_page_exists(url: str, source_wiki: str) -> bool:
        """
        Converts a branch URL into a source URL of the same page and checks if it exists there
        """
        try:
            parsed_url = parse.urlparse(url)
        except ValueError:
            error(f'Cannot parse URL "{url}"')
            return False
        # TODO: This will break if the source wiki does not support HTTPS
        parsed_url = parsed_url._replace(scheme='https')._replace(netloc=f"{source_wiki}.wikidot.com")
        original_url = parse.urlunparse(parsed_url)
        try:
            head_result = requests.head(original_url, headers={'User-Agent': USER_AGENT})
        except requests.RequestException as e:
            error(f'Request to {original_url} failed ({str(e)})')
            return False
        match head_result.status_code:
            case 200:
                return True
            case 404:
                return False
            case _:
                warning(f'Got unusual status code ({head_result.status_code}) for URL {original_url}')
                return False

def get_site_slug(url: str) -> str:
    parsed_url = parse.urlparse(url)
    path = parsed_url.path
    return path.removeprefix('/')

def snapshot_original(url: str, source_wiki_name: str = "scp-wiki", revision_id: int = 0, client: wikidot.Client = None, fail_on_not_found: bool = True) -> Optional[PathLike]:
    """
    Downloads a copy of a page's original on the source wiki, saves it to the temp directory and returns the path

    revision_id is optional and only used for file name
    """
    wd_client = client or wikidot.Client()
    page_name = get_site_slug(url)
    info(f"Saving snapshot of \"{page_name}\", revision ID is {revision_id}")
    original_page = wd_client.site.get(source_wiki_name).page.get(page_name, raise_when_not_found=False)
    if not original_page:
        if fail_on_not_found:
            error(f"Original page \"{page_name}\" not found on source wiki")
        else:
            info(f"Original page \"{page_name}\" not found on source wiki, skipping...")
        return None
    page_source = original_page.source
    filename = page_name + '-' + str(revision_id) + '.txt'
    file_path = path.join(getcwd(), 'temp', 'snapshots', source_wiki_name, filename)
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(page_source.wiki_text)
    info(f"Snapshot of \"{page_name}\" saved as {file_path}")
    return file_path

def map_target_wiki_to_source() -> dict[str, str]:
    """
    Generates a dict mapping a wiki that is translated to (target) to its original source wiki
    """
    wiki_map = {}
    if 'MONITORED_WIKIS' not in current_app.config:
        error("No monitored wikis found in config")
    for wiki in current_app.config['MONITORED_WIKIS']:
        wiki_map[wiki['target_wiki']] = wiki['source_wiki']
    return wiki_map

def snapshot_all():
    translations = Article.select(Article.link, Article.name).where(Article.is_original == False).execute()
    wiki_map = map_target_wiki_to_source()
    client = wikidot.Client()
    for tr in translations:
        target_wiki_name = parse.urlparse(tr.link).netloc.split('.')[0]
        source_wiki_name = wiki_map[target_wiki_name]
        link = str(tr.link)
        name = str(tr.name)
        
        # We check if we haven't already backed this one up
        if path.isfile(path.join(getcwd(), 'temp', 'snapshots', source_wiki_name, get_site_slug(link)+'-0.txt')): 
            info(f"Skipping {name}, file exists")
            continue

        # We check whether the page exists to not spam wikidot with unnecessary requests
        # source_page_exists only sends a single HEAD request
        #if not source_page_exists(link, source_wiki_name): 
        #    info(f"Skipping {name} (source page not found)")
        #    continue
        info(f"Making snapshot of \"{name}\"")
        file_path = snapshot_original(link, source_wiki_name, client=client, fail_on_not_found=False)
        info(f"Snapshot saved as {file_path}")

