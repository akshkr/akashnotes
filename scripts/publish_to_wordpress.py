"""
WordPress Publisher for 100-Day AI Engineering Curriculum

Publishes markdown files to WordPress via REST API with proper formatting:
- Mermaid diagrams (shortcodes for WP Mermaid plugin, or pre-rendered SVG/PNG)
- Code blocks with language classes for syntax highlighting
- Tables, blockquotes, and all standard markdown elements
- Posts organized by Phase categories with day-number ordering

Requirements:
    pip install markdown requests pygments

Optional (for mermaid-to-image conversion):
    npm install -g @mermaid-js/mermaid-cli

Usage:
    # Publish all files as drafts
    python publish_to_wordpress.py --url https://yourblog.com --user admin --password "xxxx xxxx xxxx xxxx"

    # Publish a single file
    python publish_to_wordpress.py --url https://yourblog.com --user admin --password "xxxx xxxx xxxx xxxx" --single path/to/file.md

    # Publish immediately (not draft)
    python publish_to_wordpress.py --url https://yourblog.com --user admin --password "xxxx xxxx xxxx xxxx" --publish

    # Pre-render mermaid diagrams to images instead of using shortcodes
    python publish_to_wordpress.py --url https://yourblog.com --user admin --password "xxxx xxxx xxxx xxxx" --mermaid-images
"""

import os
import re
import sys
import json
import argparse
import subprocess
import hashlib
import base64
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

import markdown
import requests
from pygments import highlight
from pygments.lexers import get_lexer_by_name, TextLexer
from pygments.formatters import HtmlFormatter

# Optional: Selenium for hosts with bot protection
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from webdriver_manager.chrome import ChromeDriverManager
    HAS_SELENIUM = True
except ImportError:
    HAS_SELENIUM = False


# ---------------------------------------------------------------------------
# Bot-protection bypass
# ---------------------------------------------------------------------------

def create_browser_session(url: str):
    """Create a persistent headless Chrome session that's past bot protection."""
    if not HAS_SELENIUM:
        print("Selenium not installed. Run: pip install selenium webdriver-manager")
        return None

    print("  Launching headless Chrome to bypass bot protection...")
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

    # Solve the initial challenge
    driver.get(url)
    for attempt in range(8):
        time.sleep(3)
        if "aes.js" not in driver.page_source:
            print(f"  Bot protection solved (attempt {attempt + 1})")
            return driver
        print(f"  Waiting for challenge... (attempt {attempt + 1})")

    print("  Could not solve bot protection after 8 attempts")
    driver.quit()
    return None


def browser_api_call(driver, url: str, method: str = "GET", payload: dict = None,
                     auth_header: str = "") -> dict:
    """Execute a WordPress REST API call using the browser's session (bypasses bot protection).

    Passes the payload as a JS argument to avoid string escaping issues with
    newlines, quotes, and special characters in HTML content.
    """

    if method == "GET":
        js = """
        var xhr = new XMLHttpRequest();
        xhr.open("GET", arguments[0], false);
        xhr.setRequestHeader("Authorization", arguments[1]);
        xhr.setRequestHeader("Content-Type", "application/json");
        xhr.send();
        return xhr.responseText;
        """
        try:
            result = driver.execute_script(js, url, auth_header)
            return json.loads(result)
        except Exception as e:
            return {"error": str(e), "raw": result if 'result' in dir() else ""}
    else:
        # For POST/PUT — pass the payload dict as a JS argument, stringify inside JS
        js = """
        var xhr = new XMLHttpRequest();
        xhr.open(arguments[0], arguments[1], false);
        xhr.setRequestHeader("Authorization", arguments[2]);
        xhr.setRequestHeader("Content-Type", "application/json");
        xhr.send(JSON.stringify(arguments[3]));
        return xhr.responseText;
        """
        try:
            result = driver.execute_script(js, method, url, auth_header, payload or {})
            return json.loads(result)
        except Exception as e:
            return {"error": str(e), "raw": result if 'result' in dir() else ""}


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class WordPressConfig:
    """WordPress connection configuration."""
    url: str
    username: str
    password: str  # Application Password (Users → Profile → Application Passwords)

    @property
    def api_base(self) -> str:
        return f"{self.url.rstrip('/')}/wp-json/wp/v2"

    @property
    def auth_header(self) -> dict:
        """Basic auth header using Application Password."""
        token = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
        return {"Authorization": f"Basic {token}"}


@dataclass
class PublishOptions:
    """Publishing options."""
    mermaid_mode: str = "shortcode"  # 'shortcode', 'image', or 'svg'
    post_status: str = "draft"       # 'draft' or 'publish'
    base_category: str = "AI Curriculum"
    delay_between_posts: float = 1.0  # seconds, avoids rate limiting
    dry_run: bool = False
    limit: int = 0                    # 0 = no limit, N = publish first N files only


# ---------------------------------------------------------------------------
# Markdown → WordPress HTML converter
# ---------------------------------------------------------------------------

class MarkdownConverter:
    """Convert markdown content to WordPress-ready HTML."""

    def __init__(self, options: PublishOptions, image_output_dir: Optional[str] = None):
        self.options = options
        self.image_output_dir = image_output_dir or "/tmp/mermaid_images"
        os.makedirs(self.image_output_dir, exist_ok=True)

    def extract_title(self, content: str) -> str:
        """Extract title from first H1 heading."""
        match = re.search(r'^# (.+)$', content, re.MULTILINE)
        return match.group(1).strip() if match else "Untitled"

    def remove_title(self, content: str) -> str:
        """Remove the first H1 heading (WordPress uses the post title field)."""
        return re.sub(r'^# .+\n*', '', content, count=1).lstrip()

    # -- Mermaid handling ---------------------------------------------------

    def convert_mermaid_shortcode(self, content: str) -> str:
        """Convert ```mermaid blocks to [mermaid] shortcodes (WP Mermaid plugin)."""
        return re.sub(
            r'```mermaid\n(.*?)\n```',
            r'[mermaid]\n\1\n[/mermaid]',
            content,
            flags=re.DOTALL
        )

    def convert_mermaid_to_image(self, mermaid_code: str) -> Optional[str]:
        """Render mermaid code to PNG using mermaid-cli (mmdc)."""
        try:
            code_hash = hashlib.md5(mermaid_code.encode()).hexdigest()[:12]
            img_name = f"diagram_{code_hash}.png"
            img_path = os.path.join(self.image_output_dir, img_name)

            if os.path.exists(img_path):
                return img_path

            temp_file = os.path.join(self.image_output_dir, "temp.mmd")
            with open(temp_file, 'w') as f:
                f.write(mermaid_code)

            config_file = os.path.join(os.path.dirname(__file__), "mermaid-config.json")
            cmd = ["mmdc", "-i", temp_file, "-o", img_path, "-b", "white", "-s", "2", "-w", "1200"]
            if os.path.exists(config_file):
                cmd.extend(["-c", config_file])
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0 and os.path.exists(img_path):
                return img_path
            else:
                print(f"    mmdc failed: {result.stderr[:200]}")
                return None

        except FileNotFoundError:
            print("    mmdc not found. Install: npm install -g @mermaid-js/mermaid-cli")
            return None
        except subprocess.TimeoutExpired:
            print("    mmdc timed out")
            return None

    def convert_mermaid_to_svg(self, mermaid_code: str) -> Optional[str]:
        """Render mermaid code to inline SVG using mermaid-cli."""
        try:
            code_hash = hashlib.md5(mermaid_code.encode()).hexdigest()[:12]
            svg_path = os.path.join(self.image_output_dir, f"diagram_{code_hash}.svg")

            if os.path.exists(svg_path):
                with open(svg_path) as f:
                    return f.read()

            temp_file = os.path.join(self.image_output_dir, "temp.mmd")
            with open(temp_file, 'w') as f:
                f.write(mermaid_code)

            config_file = os.path.join(os.path.dirname(__file__), "mermaid-config.json")
            cmd = ["mmdc", "-i", temp_file, "-o", svg_path, "-b", "white", "-w", "1200"]
            if os.path.exists(config_file):
                cmd.extend(["-c", config_file])
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0 and os.path.exists(svg_path):
                with open(svg_path) as f:
                    return f.read()
            else:
                print(f"    mmdc SVG failed: {result.stderr[:200]}")
                return None

        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None

    def replace_mermaid_blocks(self, content: str) -> tuple[str, list[str]]:
        """Replace mermaid blocks based on configured mode. Returns (content, image_paths)."""
        if self.options.mermaid_mode == "shortcode":
            return self.convert_mermaid_shortcode(content), []

        pattern = r'```mermaid\n(.*?)\n```'
        image_paths = []

        def replacer(match):
            mermaid_code = match.group(1)

            if self.options.mermaid_mode == "svg":
                svg = self.convert_mermaid_to_svg(mermaid_code)
                if svg:
                    return f'<figure class="mermaid-diagram">{svg}</figure>'

            elif self.options.mermaid_mode == "image":
                img_path = self.convert_mermaid_to_image(mermaid_code)
                if img_path:
                    image_paths.append(img_path)
                    return f'{{{{IMAGE:{img_path}}}}}'

            # Fallback to shortcode
            return f'[mermaid]\n{mermaid_code}\n[/mermaid]'

        converted = re.sub(pattern, replacer, content, flags=re.DOTALL)
        return converted, image_paths

    # -- Code block handling ------------------------------------------------

    def convert_code_blocks(self, content: str) -> str:
        """Convert fenced code blocks to Enlighter-compatible format.

        Enlighter expects: <pre data-enlighter-language="python">code</pre>
        """
        def code_replacer(match):
            lang = match.group(1) or "generic"
            code = match.group(2)
            # Escape HTML entities inside code
            code = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            return f'<pre data-enlighter-language="{lang}">{code}</pre>'

        return re.sub(
            r'```(\w*)\n(.*?)\n```',
            code_replacer,
            content,
            flags=re.DOTALL
        )

    # -- SWE bridging callouts ----------------------------------------------

    def convert_blockquotes(self, content: str) -> str:
        """Convert > blockquotes to styled HTML divs for better rendering."""
        # Convert the "Coming from Software Engineering?" callouts to styled divs
        def callout_replacer(match):
            text = match.group(1).strip()
            # Remove leading > from each line
            lines = [line.lstrip('>').strip() for line in text.split('\n')]
            inner = ' '.join(lines)
            return (
                f'<div style="background:#f0f7ff;border-left:4px solid #2563eb;'
                f'padding:16px;margin:16px 0;border-radius:4px;">'
                f'{inner}</div>'
            )

        # Match multi-line blockquotes that start with > **Coming from
        content = re.sub(
            r'(> \*\*Coming from Software Engineering\?\*\*.*?)(?=\n\n|\n---|\Z)',
            callout_replacer,
            content,
            flags=re.DOTALL
        )
        return content

    # -- Main conversion pipeline -------------------------------------------

    def convert(self, content: str) -> tuple[str, str, list[str]]:
        """
        Full conversion pipeline: markdown → WordPress HTML.

        Returns: (title, html_content, image_paths_to_upload)
        """
        title = self.extract_title(content)
        content = self.remove_title(content)

        # 1. Handle mermaid diagrams (before markdown conversion)
        content, image_paths = self.replace_mermaid_blocks(content)

        # 2. Handle SWE bridging callouts
        content = self.convert_blockquotes(content)

        # 3. Handle code blocks (before markdown conversion to avoid double-processing)
        content = self.convert_code_blocks(content)

        # 4. Convert remaining markdown to HTML
        html = markdown.markdown(
            content,
            extensions=['tables', 'toc', 'nl2br']
        )

        # 5. Clean up: remove empty paragraphs
        html = re.sub(r'<p>\s*</p>', '', html)

        return title, html, image_paths


# ---------------------------------------------------------------------------
# WordPress REST API publisher
# ---------------------------------------------------------------------------

class WordPressPublisher:
    """Publish content to WordPress via REST API."""

    def __init__(self, config: WordPressConfig, options: PublishOptions):
        self.config = config
        self.options = options
        self.converter = MarkdownConverter(options)
        self.driver = None  # Selenium browser, initialized on connect

        # Cache category IDs
        self._category_cache: dict[str, int] = {}

    def _api_call(self, endpoint: str, method: str = "GET", payload: dict = None) -> dict:
        """Make a WordPress REST API call via the browser session."""
        url = f"{self.config.api_base}/{endpoint.lstrip('/')}"
        result = browser_api_call(
            self.driver, url, method=method, payload=payload,
            auth_header=f"Basic {base64.b64encode(f'{self.config.username}:{self.config.password}'.encode()).decode()}"
        )
        return result

    def test_connection(self) -> bool:
        """Launch browser, bypass bot protection, verify WordPress credentials."""
        self.driver = create_browser_session(self.config.url)
        if not self.driver:
            return False

        try:
            result = self._api_call("users/me")
            if "id" in result:
                print(f"Connected as: {result.get('name', 'unknown')}")
                return True
            else:
                print(f"Auth failed: {json.dumps(result)[:200]}")
                return False
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False

    def cleanup(self):
        """Close the browser session."""
        if self.driver:
            self.driver.quit()
            self.driver = None

    def get_or_create_category(self, name: str, parent_id: int = 0) -> Optional[int]:
        """Get existing category ID or create a new one."""
        if name in self._category_cache:
            return self._category_cache[name]

        # Search existing
        result = self._api_call(f"categories?search={name}&per_page=100")
        if isinstance(result, list):
            for cat in result:
                if cat.get("name", "").lower() == name.lower():
                    self._category_cache[name] = cat["id"]
                    return cat["id"]

        # Create new
        result = self._api_call("categories", method="POST", payload={"name": name, "parent": parent_id})
        if "id" in result:
            self._category_cache[name] = result["id"]
            return result["id"]
        else:
            print(f"    Failed to create category '{name}': {json.dumps(result)[:200]}")
            return None

    def upload_image(self, image_path: str) -> Optional[str]:
        """Upload image to WordPress media library via browser, return URL."""
        filename = os.path.basename(image_path)
        try:
            with open(image_path, 'rb') as f:
                image_data = f.read()

            # Convert image to base64 and upload via fetch in the browser
            img_b64 = base64.b64encode(image_data).decode()
            auth_b64 = base64.b64encode(f"{self.config.username}:{self.config.password}".encode()).decode()
            url = f"{self.config.api_base}/media"

            js = f"""
            var binary = atob("{img_b64}");
            var bytes = new Uint8Array(binary.length);
            for (var i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
            var xhr = new XMLHttpRequest();
            xhr.open("POST", "{url}", false);
            xhr.setRequestHeader("Authorization", "Basic {auth_b64}");
            xhr.setRequestHeader("Content-Type", "image/png");
            xhr.setRequestHeader("Content-Disposition", 'attachment; filename="{filename}"');
            xhr.send(bytes.buffer);
            return xhr.responseText;
            """

            result_text = self.driver.execute_script(js)
            result = json.loads(result_text)
            return result.get("source_url")

        except Exception as e:
            print(f"    Image upload error: {e}")
            return None

    def publish_post(
        self,
        title: str,
        content: str,
        category_ids: list[int],
        image_paths: list[str] = None,
        menu_order: int = 0
    ) -> Optional[int]:
        """Create a single WordPress post."""

        # Upload images and replace placeholders
        if image_paths:
            for img_path in image_paths:
                img_url = self.upload_image(img_path)
                if img_url:
                    placeholder = f'{{{{IMAGE:{img_path}}}}}'
                    content = content.replace(
                        placeholder,
                        f'<figure class="mermaid-diagram">'
                        f'<img src="{img_url}" alt="Diagram" loading="lazy" />'
                        f'</figure>'
                    )

        if self.options.dry_run:
            print(f"    [DRY RUN] Would publish: {title}")
            return 0

        payload = {
            "title": title,
            "content": content,
            "status": self.options.post_status,
            "categories": [c for c in category_ids if c],
            "menu_order": menu_order,
        }

        result = self._api_call("posts", method="POST", payload=payload)

        if "id" in result:
            post_id = result["id"]
            post_link = result.get("link", "")
            print(f"    Published (ID: {post_id}) {post_link}")
            return post_id
        else:
            print(f"    Failed: {json.dumps(result)[:300]}")
            return None

    def publish_file(self, filepath: str, category_ids: list[int], order: int = 0) -> Optional[int]:
        """Convert and publish a single markdown file."""
        with open(filepath, 'r') as f:
            content = f.read()

        title, html, image_paths = self.converter.convert(content)
        return self.publish_post(title, html, category_ids, image_paths, menu_order=order)

    def publish_curriculum(self, base_path: str):
        """Publish all Day_* files from the Phase_*/Day_*/ directory structure."""
        base = Path(base_path)
        published = 0
        failed = 0
        skipped = 0

        # Get or create the top-level category
        base_cat_id = self.get_or_create_category(self.options.base_category)

        # Walk Phase directories in order
        phase_dirs = sorted(base.glob("Phase_*"))
        if not phase_dirs:
            print(f"No Phase_* directories found in {base_path}")
            return

        for phase_dir in phase_dirs:
            phase_name = phase_dir.name.replace("_", " ")  # "Phase 1 LLM Foundations"
            # Clean up name: "Phase 1 LLM Foundations" → "Phase 1: LLM Foundations"
            phase_name = re.sub(r'^(Phase \d+) ', r'\1: ', phase_name)
            phase_cat_id = self.get_or_create_category(phase_name, parent_id=base_cat_id or 0)

            print(f"\n{'='*60}")
            print(f"  {phase_name}")
            print(f"{'='*60}")

            # Walk Day directories in order
            day_dirs = sorted(phase_dir.glob("Day_*"))
            for day_dir in day_dirs:
                # Check limit
                if self.options.limit > 0 and published >= self.options.limit:
                    print(f"\n  Reached --limit {self.options.limit}, stopping.")
                    break

                # Find the markdown file inside
                md_files = list(day_dir.glob("*.md"))
                if not md_files:
                    print(f"  Skipping {day_dir.name}: no .md file")
                    skipped += 1
                    continue

                md_file = md_files[0]

                # Extract day number for ordering
                day_match = re.search(r'Day_(\d+)', day_dir.name)
                day_num = int(day_match.group(1)) if day_match else 0

                print(f"\n  [{day_num:03d}] {md_file.name}")

                category_ids = [c for c in [base_cat_id, phase_cat_id] if c]
                result = self.publish_file(str(md_file), category_ids, order=day_num)

                if result is not None:
                    published += 1
                else:
                    failed += 1

                # Rate limit delay
                if self.options.delay_between_posts > 0:
                    time.sleep(self.options.delay_between_posts)

            # Break outer loop too if limit reached
            if self.options.limit > 0 and published >= self.options.limit:
                break

        print(f"\n{'='*60}")
        print(f"  DONE")
        print(f"  Published: {published}")
        print(f"  Failed:    {failed}")
        print(f"  Skipped:   {skipped}")
        print(f"{'='*60}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Publish 100-Day AI Curriculum to WordPress via REST API"
    )
    parser.add_argument("--url", required=True, help="WordPress site URL")
    parser.add_argument("--user", required=True, help="WordPress username")
    parser.add_argument("--password", required=True, help="Application Password")
    parser.add_argument(
        "--path", default="/Users/akash/Personal/notes",
        help="Path to curriculum directory (default: /Users/akash/Personal/notes)"
    )
    parser.add_argument("--publish", action="store_true", help="Publish immediately (default: draft)")
    parser.add_argument("--single", help="Publish a single markdown file")
    parser.add_argument(
        "--mermaid", choices=["shortcode", "image", "svg"], default="shortcode",
        help="Mermaid rendering mode (default: shortcode)"
    )
    parser.add_argument("--category", default="AI Curriculum", help="Top-level category name")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between posts in seconds")
    parser.add_argument("--dry-run", action="store_true", help="Preview without publishing")
    parser.add_argument("--limit", type=int, default=0, help="Publish only first N files (0 = all)")

    args = parser.parse_args()

    config = WordPressConfig(
        url=args.url,
        username=args.user,
        password=args.password
    )

    options = PublishOptions(
        mermaid_mode=args.mermaid,
        post_status="publish" if args.publish else "draft",
        base_category=args.category,
        delay_between_posts=args.delay,
        dry_run=args.dry_run,
        limit=args.limit
    )

    publisher = WordPressPublisher(config, options)

    # Test connection first
    print("Testing WordPress connection...")
    if not publisher.test_connection():
        sys.exit(1)
    print()

    # Publish
    try:
        if args.single:
            base_cat_id = publisher.get_or_create_category(options.base_category)
            publisher.publish_file(args.single, [base_cat_id] if base_cat_id else [])
        else:
            publisher.publish_curriculum(args.path)
    finally:
        publisher.cleanup()


if __name__ == "__main__":
    main()
