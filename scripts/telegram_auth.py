"""One-shot script to authenticate a Telegram user account via MTProto and generate
a session string for use with the Telegram Stories API.

Run with:  python scripts/telegram_auth.py

Requirements: telethon>=1.36  (pip install telethon)

Steps this script performs:
  1. Prompt for api_id and api_hash (get these from https://my.telegram.org/apps).
  2. Prompt for your phone number and complete the SMS / Telegram code flow.
  3. Optionally enter your 2FA password if you have one set.
  4. Print the session string — paste it into Settings > Telegram Session String.
  5. Verify access to your channel by fetching its entity and checking admin rights.
"""

import asyncio
import sys


async def main() -> None:
    try:
        from telethon import TelegramClient
        from telethon.sessions import StringSession
        from telethon.tl.functions.channels import GetParticipantRequest
        from telethon.tl.types import ChannelParticipantAdmin, ChannelParticipantCreator
    except ImportError:
        print("telethon is not installed. Run:  pip install 'telethon>=1.36'")
        sys.exit(1)

    print("=" * 60)
    print("Telegram MTProto auth setup")
    print("=" * 60)
    print()
    print("Before starting, you need an api_id and api_hash from:")
    print("  https://my.telegram.org/apps")
    print("Log in with your personal account → API development tools")
    print("→ create a new app (name/platform don't matter) → copy the")
    print("  App api_id and App api_hash shown on the page.")
    print()

    api_id_str = input("Enter api_id (integer): ").strip()
    if not api_id_str.isdigit():
        print("api_id must be an integer.")
        sys.exit(1)
    api_id = int(api_id_str)
    api_hash = input("Enter api_hash: ").strip()

    print()
    channel_id = input(
        "Enter your channel username or ID (e.g. @mychannel or -1001234567890): "
    ).strip()

    print()
    print("Starting auth flow — you will receive a code via Telegram or SMS...")
    print()

    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.start()

    session_string = client.session.save()

    print()
    print("=" * 60)
    print("Auth successful!")
    print()
    print("SESSION STRING (copy everything between the lines):")
    print("-" * 60)
    print(session_string)
    print("-" * 60)
    print()
    print("Paste this into Settings > Telegram Session String.")
    print()

    # Verify channel access
    print(f"Verifying access to channel: {channel_id} ...")
    try:
        entity = await client.get_entity(channel_id)
        print(f"  Channel found: {getattr(entity, 'title', channel_id)}")

        me = await client.get_me()
        try:
            participant = await client(GetParticipantRequest(channel=entity, participant=me))
            role = participant.participant
            if isinstance(role, (ChannelParticipantCreator, ChannelParticipantAdmin)):
                print("  Admin rights confirmed — stories posting should work.")
            else:
                print("  WARNING: you are a member but not an admin.")
                print("  Story posting requires admin rights on the channel.")
        except Exception as exc:
            print(f"  Could not verify admin rights: {exc}")
            print("  Make sure your account is an admin on this channel.")
    except Exception as exc:
        print(f"  ERROR: could not access channel: {exc}")
        print("  Check the channel ID/username and try again.")

    await client.disconnect()
    print()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
