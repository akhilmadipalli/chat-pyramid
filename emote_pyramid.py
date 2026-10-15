"""
Send a pyramid of emotes to a Twitch chat using the plain IRC interface.

Usage:
    python emote_pyramid.py --channel yourchannel --emote Kappa --height 5

Setup:
    1. Get an OAuth token with the chat:edit scope (for example from
       https://twitchtokengenerator.com or your own registered Twitch app).
    2. Set environment variables:
         TWITCH_NICK   your bot or account username (lowercase)
         TWITCH_TOKEN  the token, with or without the "oauth:" prefix
"""

import argparse
import os
import socket
import sys
import time

HOST = "irc.chat.twitch.tv"
PORT = 6667
MAX_MESSAGE_LEN = 500  # Twitch chat limit


def build_rows(emote: str, height: int) -> list[str]:
    """Return the messages for a pyramid: 1..height then height-1..1."""
    up = [" ".join([emote] * i) for i in range(1, height + 1)]
    down = up[-2::-1]  # mirror, skipping the widest row
    return up + down


def connect(nick: str, token: str, channel: str) -> socket.socket:
    if not token.startswith("oauth:"):
        token = "oauth:" + token
    sock = socket.socket()
    sock.connect((HOST, PORT))
    sock.send(f"PASS {token}\r\n".encode("utf-8"))
    sock.send(f"NICK {nick}\r\n".encode("utf-8"))
    sock.send(f"JOIN #{channel}\r\n".encode("utf-8"))
    sock.settimeout(10)
    # Wait for the welcome message so we know login worked.
    buf = ""
    while "001" not in buf:
        data = sock.recv(2048).decode("utf-8", errors="ignore")
        if not data:
            raise ConnectionError("Connection closed during login")
        buf += data
        if "Login authentication failed" in buf:
            raise PermissionError("Bad token or username")
    return sock


def send_message(sock: socket.socket, channel: str, text: str) -> None:
    sock.send(f"PRIVMSG #{channel} :{text}\r\n".encode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Send an emote pyramid to Twitch chat")
    parser.add_argument("--channel", required=True, help="channel name, no #")
    parser.add_argument("--emote", required=True, help="emote name, e.g. Kappa")
    parser.add_argument("--height", type=int, default=5, help="rows in the rising half")
    parser.add_argument(
        "--delay",
        type=float,
        default=1.6,
        help="seconds between messages (default stays under the 20 per 30s limit)",
    )
    parser.add_argument("--dry-run", action="store_true", help="print rows, do not send")
    args = parser.parse_args()

    rows = build_rows(args.emote, args.height)

    too_long = [r for r in rows if len(r) > MAX_MESSAGE_LEN]
    if too_long:
        sys.exit(f"Widest row is {len(rows[args.height - 1])} chars, over {MAX_MESSAGE_LEN}. Lower --height.")

    if args.dry_run:
        print("\n".join(rows))
        return

    nick = os.environ.get("TWITCH_NICK")
    token = os.environ.get("TWITCH_TOKEN")
    if not nick or not token:
        sys.exit("Set TWITCH_NICK and TWITCH_TOKEN environment variables first.")

    sock = connect(nick.lower(), token, args.channel.lower())
    try:
        for row in rows:
            send_message(sock, args.channel.lower(), row)
            print(f"sent: {row}")
            time.sleep(args.delay)
    finally:
        sock.close()


if __name__ == "__main__":
    main()
