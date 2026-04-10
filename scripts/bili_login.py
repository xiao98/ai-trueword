"""B站扫码登录 — 在服务器上运行，用手机扫码登录Bot账号。

Usage:
    python3 scripts/bili_login.py

会在终端显示二维码，用B站App扫码登录后自动保存cookie到 .env 文件。
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bilibili_api.login import login_with_qrcode, QrCodeLoginEvents
from bilibili_api import Credential


ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")


def update_env(credential: Credential):
    """Update .env file with new Bilibili credentials."""
    cookies = credential.get_cookies()

    updates = {
        "BILI_SESSDATA": cookies.get("SESSDATA", ""),
        "BILI_BILI_JCT": cookies.get("bili_jct", ""),
        "BILI_BUVID3": cookies.get("buvid3", ""),
        "BILI_DEDEUSERID": cookies.get("DedeUserID", ""),
        "BILI_BUVID4": cookies.get("buvid4", ""),
        "BILI_AC_TIME_VALUE": cookies.get("ac_time_value", ""),
    }

    # Read existing .env
    lines = []
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH) as f:
            lines = f.readlines()

    # Update or append
    existing_keys = set()
    new_lines = []
    for line in lines:
        key = line.split("=", 1)[0].strip()
        if key in updates:
            new_lines.append(f"{key}={updates[key]}\n")
            existing_keys.add(key)
        else:
            new_lines.append(line)

    for key, val in updates.items():
        if key not in existing_keys:
            new_lines.append(f"{key}={val}\n")

    with open(ENV_PATH, "w") as f:
        f.writelines(new_lines)

    print(f"\n✓ Cookie已保存到 {ENV_PATH}")


async def main():
    print("=" * 40)
    print("B站扫码登录")
    print("=" * 40)
    print("\n请用B站App扫描下方二维码：\n")

    credential = await login_with_qrcode()

    if credential:
        print("\n✓ 登录成功！")
        cookies = credential.get_cookies()
        print(f"  UID: {cookies.get('DedeUserID', 'unknown')}")

        update_env(credential)

        print("\n现在可以重启Bot：")
        print("  systemctl restart ai-trueword-bilibili")
    else:
        print("\n✗ 登录失败，请重试。")


if __name__ == "__main__":
    asyncio.run(main())
