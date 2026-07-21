"""Generate a Telethon StringSession token interactively."""

import asyncio
import getpass
import sys
from pathlib import Path

from telethon import TelegramClient, errors
from telethon.sessions import StringSession

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


def _load_env_credentials() -> tuple[int, str]:
    """Load API credentials from the project .env file."""
    if not ENV_FILE.exists():
        print(f".env not found at {ENV_FILE}", file=sys.stderr)
        sys.exit(1)

    env_data: dict[str, str] = {}
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env_data[key.strip()] = value.strip()

    raw_id = env_data.get("TELETHON_API_ID", "")
    api_hash = env_data.get("TELETHON_API_HASH", "")

    if not raw_id or not api_hash:
        print("TELETHON_API_ID / TELETHON_API_HASH missing from .env", file=sys.stderr)
        sys.exit(1)

    try:
        api_id = int(raw_id)
    except ValueError:
        print("TELETHON_API_ID must be an integer.", file=sys.stderr)
        sys.exit(1)

    return api_id, api_hash


async def main() -> None:
    api_id, api_hash = _load_env_credentials()

    phone = input("Phone number (with country code, e.g. +880...): ").strip()
    if not phone:
        print("Phone number cannot be empty.", file=sys.stderr)
        return

    session = StringSession()

    client = TelegramClient(session, api_id, api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            await client.send_code_request(phone)
            code = input("Enter the code you received: ").strip()
            try:
                await client.sign_in(phone=phone, code=code)
            except errors.PhoneCodeInvalidError:
                print("Invalid code. Telegram codes expire quickly; run it again and use the newest code.", file=sys.stderr)
                return
            except errors.PhoneCodeExpiredError:
                print("Code expired. Run it again for a fresh code.", file=sys.stderr)
                return
            except errors.SessionPasswordNeededError:
                password = getpass.getpass("2FA password: ")
                await client.sign_in(password=password)

        string_session = client.session.save()
    finally:
        await client.disconnect()

    print("\n=== String Session ===")
    print(string_session)
    print("======================\n")
    print("Save this somewhere safe. Anyone with this string has full account access.")


if __name__ == "__main__":
    asyncio.run(main())
