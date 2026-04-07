"""
Delete all posts from a WordPress site.

Usage:
    python clean_wordpress.py --url https://akashnotes.page.gd --user admin --password "xxxx xxxx xxxx xxxx"
"""

import argparse
import base64
import json
import time
import sys

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    print("Install dependencies: pip install selenium webdriver-manager")
    sys.exit(1)


def create_browser(url):
    """Launch headless Chrome and solve bot protection."""
    options = ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()),
        options=options
    )

    print("Solving bot protection...")
    driver.get(url)
    for attempt in range(8):
        time.sleep(3)
        if "aes.js" not in driver.page_source:
            print(f"  Done (attempt {attempt + 1})")
            return driver
        print(f"  Waiting... (attempt {attempt + 1})")

    print("Could not bypass bot protection")
    driver.quit()
    return None


def api_call(driver, url, method="GET", auth_header=""):
    """Make an API call via the browser session."""
    if method == "GET":
        js = """
        var xhr = new XMLHttpRequest();
        xhr.open("GET", arguments[0], false);
        xhr.setRequestHeader("Authorization", arguments[1]);
        xhr.send();
        return xhr.responseText;
        """
        result = driver.execute_script(js, url, auth_header)
    else:
        js = """
        var xhr = new XMLHttpRequest();
        xhr.open(arguments[0], arguments[1], false);
        xhr.setRequestHeader("Authorization", arguments[2]);
        xhr.send();
        return xhr.responseText;
        """
        result = driver.execute_script(js, method, url, auth_header)

    return json.loads(result) if result else {}


def main():
    parser = argparse.ArgumentParser(description="Delete all posts from WordPress")
    parser.add_argument("--url", required=True, help="WordPress site URL")
    parser.add_argument("--user", required=True, help="WordPress username")
    parser.add_argument("--password", required=True, help="Application Password")
    parser.add_argument("--force", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    api_base = f"{args.url.rstrip('/')}/wp-json/wp/v2"
    auth = f"Basic {base64.b64encode(f'{args.user}:{args.password}'.encode()).decode()}"

    driver = create_browser(args.url)
    if not driver:
        sys.exit(1)

    try:
        # Get total post count
        posts = api_call(driver, f"{api_base}/posts?per_page=1&status=any", auth_header=auth)
        if isinstance(posts, dict) and "code" in posts:
            print(f"Error: {posts}")
            sys.exit(1)

        # Fetch all posts (paginate)
        all_posts = []
        page = 1
        while True:
            posts = api_call(
                driver,
                f"{api_base}/posts?per_page=100&page={page}&status=any",
                auth_header=auth
            )
            if not posts or not isinstance(posts, list):
                break
            all_posts.extend(posts)
            if len(posts) < 100:
                break
            page += 1

        if not all_posts:
            print("No posts found.")
            return

        print(f"\nFound {len(all_posts)} posts:")
        for p in all_posts[:10]:
            print(f"  - [{p['id']}] {p['title']['rendered']}")
        if len(all_posts) > 10:
            print(f"  ... and {len(all_posts) - 10} more")

        # Confirm
        if not args.force:
            confirm = input(f"\nDelete ALL {len(all_posts)} posts permanently? (yes/no): ")
            if confirm.lower() != "yes":
                print("Cancelled.")
                return

        # Delete each post (force=true bypasses trash)
        deleted = 0
        for post in all_posts:
            post_id = post["id"]
            title = post["title"]["rendered"][:50]
            result = api_call(
                driver,
                f"{api_base}/posts/{post_id}?force=true",
                method="DELETE",
                auth_header=auth
            )
            if "deleted" in result and result["deleted"]:
                print(f"  Deleted: [{post_id}] {title}")
                deleted += 1
            else:
                print(f"  Failed:  [{post_id}] {title} — {json.dumps(result)[:100]}")

        print(f"\nDone. Deleted {deleted}/{len(all_posts)} posts.")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
