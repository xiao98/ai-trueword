"""B站扫码登录 — 在服务器上运行，用手机扫码登录Bot账号。

Usage:
    python3 scripts/bili_login.py

会在终端显示二维码，用B站App扫码登录后自动保存cookie到 .env 文件。
"""

import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bilibili_api.login_v2 import QrCodeLogin, QrCodeLoginEvents
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

    qr = QrCodeLogin()
    await qr.generate_qrcode()

    # 获取二维码图片URL供手机扫码
    qr_pic = qr.get_qrcode_picture()
    print(f"\n方法1: 用手机浏览器打开此链接，然后长按识别二维码：")
    print(f"  {qr_pic.url}")
    print(f"\n方法2: 终端二维码（需要终端窗口足够大）：")
    try:
        print(qr.get_qrcode_terminal())
    except Exception:
        pass

    print("\n等待扫码...")

    while True:
        state = await qr.check_state()

        if state == QrCodeLoginEvents.SCAN:
            print("  已扫码，请在手机上确认...")
        elif state == QrCodeLoginEvents.CONF:
            print("  已确认，正在登录...")
        elif state == QrCodeLoginEvents.DONE:
            print("\n✓ 登录成功！")
            credential = qr.get_credential()
            cookies = credential.get_cookies()
            print(f"  UID: {cookies.get('DedeUserID', 'unknown')}")

            update_env(credential)

            print("\n现在可以重启Bot：")
            print("  systemctl restart ai-trueword-bilibili")
            return
        elif state == QrCodeLoginEvents.TIMEOUT:
            print("\n✗ 二维码已过期，请重新运行脚本。")
            return

        await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
