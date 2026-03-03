from os import PathLike
from connectors.discord import DiscordClient, DiscordException
from db import User
from PIL import Image
from io import BytesIO
from logging import warning, error, debug, info
from os.path import join
from typing import List, Optional
import time

def update_nicknames_task(override_users: Optional[List[User]] = None):
    users = override_users or list(User.select())

    info(f"Updating discord display names of {len(users)} users")

    updated = skipped = 0

    for user in users:
        if not user.discord:
            warning(f"Skipping nickname update for {user.nickname}")
            skipped += 1
            continue
        try:
            new_nickname = DiscordClient.get_global_username(user.discord)
        except DiscordException:
            warning(f"Skipping nickname update for {user.nickname} (API error)")
            skipped += 1
            continue
        if new_nickname != None:
            user.display_name = new_nickname
            user.save()
            updated += 1
        time.sleep(0.2) # Wait a bit so the API doesn't 429
    info(f"Display name update complete - {updated} updated, {skipped} skipped due to error")

def download_avatars_task(av_path: str | PathLike = './temp/avatar', override_users: Optional[List[User]] = None):
    users = override_users or list(User.select(User.discord, User.avatar_hash, User.nickname, User.id).where(User.discord.is_null(False)))

    info(f"Downloading discord avatars of {len(users)} users")

    updated = skipped = cached = 0

    for user in users:
        try:
            discord_data = DiscordClient.get_user(user.discord)
        except DiscordException:
            warning(f"Skipping avatar download for {user.discord} (API request failed)")
            skipped += 1
            continue
        if not discord_data:
            warning(f"Skipping avatar update for {user.nickname} ({user.discord}) (Couldn't fetch API data)")
            skipped += 1
            continue
        # Check that the avatar hashes are different before downloading the avatar
        if user.avatar_hash is None or user.avatar_hash != discord_data['avatar']:
            User.update(avatar_hash=discord_data['avatar']).where(User.id == user.id).execute()
            try:
                avatar = DiscordClient.get_avatar(user.discord)
            except DiscordException:
                warning(f"Skipping avatar download for {user.discord} (API request failed)")
                skipped += 1
                continue
            if avatar is not None:
                with open(join(av_path,f'{user.discord}.png'), 'wb') as file:
                    file.write(avatar)
                    Image.open(BytesIO(avatar)).resize((64, 64), Image.Resampling.NEAREST).save(join(av_path,f'{user.discord}_thumb.png')) # Create a 64x64 thumnail and save it as [ID]_thumb.png

                time.sleep(0.5) # Wait for a bit so we don't hit the rate limit
                updated += 1
            else:
                skipped += 1
                error(f"Avatar download failed for {user.nickname} ({user.discord})")
        else:
            cached += 1
            debug(f"Skipping avatar update for {user.discord} (Avatar hashes match)")

    info(f"Avatar update complete - {updated} downloaded, {cached} cached, {skipped} skipped due to error")