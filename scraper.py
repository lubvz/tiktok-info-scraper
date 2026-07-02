import requests
import re
import urllib.parse
from bs4 import BeautifulSoup
import os
import sys


def print_banner():
    blue = '\033[94m'
    yellow = '\033[93m'
    reset = '\033[0m'
    
    banner = f"""{blue}
.__       ___.                 
|  |  __ _\_ |_____  __________
|  | |  |  \ __ \  \/ /\___   /
|  |_|  |  / \_\ \   /  /    / 
|____/____/|___  /\_/  /_____ \

    {reset}
{blue}         Tiktok user info scraper{reset}

{blue}[1] search by username{reset}
{blue}[2] search by user id{reset}
{blue}[3] exit{reset}

{yellow}enter your choice (1-3): {reset}"""
    print(banner, end='')


def extract_data(html_content: str, bio: str) -> dict:
    data = {
        "social_links": [],
        "emails": []
    }
    seen_links = set()

    def add_link(text: str, url: str | None = None):
        clean_url = (url or text).replace("\\u002F", "/")
        if clean_url not in seen_links:
            seen_links.add(clean_url)
            if url:
                data["social_links"].append(f"{text}: {clean_url}")
            else:
                data["social_links"].append(text)

    for full_url, target in re.findall(
        r'href="(https://www\.tiktok\.com/link/v2\?[^"]*?scene=bio_url[^"]*?target=([^"&]+))"', html_content
    ):
        decoded = urllib.parse.unquote(target)
        text_match = re.search(
            rf'href="{re.escape(full_url)}"[^>]*>.*?<span[^>]*SpanLink[^>]*>([^<]+)</span>',
            html_content, re.DOTALL
        )
        add_link(text_match.group(1) if text_match else decoded, decoded)

    for link, _ in re.findall(r'"bioLink":\{"link":"([^"]+)","risk":(\d+)\}', html_content):
        add_link("bio link", link)

    for span_text in re.findall(r'<span[^>]*class="[^"]*SpanLink[^"]*">([^<]+)</span>', html_content):
        if "." in span_text and " " not in span_text:
            add_link(span_text)

    social_patterns = {
        "instagram": r'[iI][gG]:\s*@?([a-zA-Z0-9._]+)',
        "snapchat": r'(?:[sS][cC]|[sS]napchat):\s*@?([a-zA-Z0-9._]+)',
        "twitter/x": r'(?:[tT]witter|[xX]):\s*@?([a-zA-Z0-9._]+)',
        "facebook": r'[fF][bB]:\s*@?([a-zA-Z0-9._]+)',
        "youtube": r'(?:[yY][tT]|[yY]outube):\s*@?([a-zA-Z0-9._]+)',
        "telegram": r'[tT]elegram:\s*@?([a-zA-Z0-9._]+)',
    }
    
    for platform, pattern in social_patterns.items():
        match = re.search(pattern, bio)
        if match:
            username = match.group(1)
            prefix = "@" if platform in ("instagram", "twitter/x", "telegram") else ""
            add_link(f"{platform}", f"{prefix}{username}")

    email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', bio)
    if email_match:
        data["emails"].append(email_match.group(0))

    return data


def get_user_info(identifier: str, by_id: bool = False):
    if identifier.startswith('@'):
        identifier = identifier[1:]
        
    url = f"https://www.tiktok.com/@{identifier}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"error fetching profile: {e}")
        return

    html_content = response.text
    
    patterns = {
        'user_id': r'"webapp.user-detail":{"userInfo":{"user":{"id":"(\d+)"',
        'unique_id': r'"uniqueId":"(.*?)"',
        'nickname': r'"nickname":"(.*?)"',
        'followers': r'"followerCount":(\d+)',
        'following': r'"followingCount":(\d+)',
        'likes': r'"heartCount":(\d+)',
        'videos': r'"videoCount":(\d+)',
        'signature': r'"signature":"(.*?)"',
        'verified': r'"verified":(true|false)',
        'secUid': r'"secUid":"(.*?)"',
        'privateAccount': r'"privateAccount":(true|false)',
        'region': r'"region":"([^"]*)"',
        'profile_pic': r'"avatarLarger":"(.*?)"'
    }
    
    info = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, html_content)
        info[key] = match.group(1) if match else "n/a"

    if info['profile_pic'] != "n/a":
        info['profile_pic'] = info['profile_pic'].replace('\\u002F', '/')

    bio = info.get('signature', "").replace('\\n', '\n')
    social_data = extract_data(html_content, bio)

    print("\n--- user information ---")
    print(f"id: {info['user_id']}")
    print(f"username: {info['unique_id']}")
    print(f"nickname: {info['nickname']}")
    print(f"verified: {info['verified']}")
    print(f"private: {info['privateAccount']}")
    print(f"region: {info['region']}")
    print(f"followers: {info['followers']}")
    print(f"following: {info['following']}")
    print(f"total likes: {info['likes']}")
    print(f"videos: {info['videos']}")
    print(f"secuid: {info['secUid']}")
    
    print("\n--- biography ---")
    print(bio)
    
    if social_data['social_links']:
        print("\n--- social links ---")
        for link in social_data['social_links']:
            print(link)
            
    if social_data['emails']:
        print("\n--- emails ---")
        for email in social_data['emails']:
            print(email)

    if info['profile_pic'] != "n/a" and info['profile_pic'].startswith("http"):
        save_choice = input("\ndownload profile picture? (y/n): ").strip().lower()
        if save_choice == 'y':
            try:
                pic_res = requests.get(info['profile_pic'])
                if pic_res.status_code == 200:
                    filename = f"{info['unique_id']}_profile.jpg"
                    with open(filename, "wb") as f:
                        f.write(pic_res.content)
                    print(f"saved as {filename}")
                else:
                    print("failed to download image.")
            except Exception as e:
                print(f"error: {e}")


def menu():
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print_banner()
        
        choice = input().strip()
        
        if choice == "1":
            username = input("enter tiktok username: ").strip()
            if username:
                get_user_info(username, by_id=False)
                input("\npress enter to continue")
            else:
                print("username cannot be empty")
                input("\npress enter to continue")
                
        elif choice == "2":
            user_id = input("enter tiktok user id: ").strip()
            if user_id:
                get_user_info(user_id, by_id=True)
                input("\npress enter to continue...")
            else:
                print("user id cannot be empty!")
                input("\npress enter to continue...")
                
        elif choice == "3":
            print("exiting...")
            sys.exit(0)
            
        else:
            print("invalid choice! please enter 1, 2, or 3.")
            input("\npress enter to continue...")


if __name__ == "__main__":
    menu()
