"""
WordPress Publisher for AI Curriculum Blog

This script publishes markdown files to WordPress with proper formatting:
- Mermaid diagrams (converted to shortcodes or images)
- Python code blocks (syntax highlighted)
- Tables and other markdown elements

Requirements:
    pip install python-wordpress-xmlrpc markdown requests

Optional (for mermaid to image conversion):
    npm install -g @mermaid-js/mermaid-cli

Usage:
    python publish_to_wordpress.py --url https://yourblog.com --user admin --password app_password
"""

import os
import re
import argparse
import subprocess
import hashlib
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

import markdown
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods.posts import NewPost, GetPosts
from wordpress_xmlrpc.methods.media import UploadFile


@dataclass
class WordPressConfig:
    """WordPress connection configuration."""
    url: str
    username: str
    password: str  # Use Application Password, not main password

    @property
    def xmlrpc_url(self) -> str:
        return f"{self.url.rstrip('/')}/xmlrpc.php"


@dataclass
class PublishOptions:
    """Publishing options."""
    convert_mermaid_to_images: bool = False
    post_status: str = "draft"  # 'draft' or 'publish'
    base_category: str = "AI Curriculum"


class MarkdownConverter:
    """Convert markdown content for WordPress."""

    def __init__(self, options: PublishOptions, image_output_dir: Optional[str] = None):
        self.options = options
        self.image_output_dir = image_output_dir or "/tmp/mermaid_images"
        os.makedirs(self.image_output_dir, exist_ok=True)

    def convert_mermaid_to_shortcode(self, content: str) -> str:
        """Convert mermaid code blocks to WordPress shortcode (WP Mermaid plugin)."""
        pattern = r'```mermaid\n(.*?)\n```'
        replacement = r'[mermaid]\n\1\n[/mermaid]'
        return re.sub(pattern, replacement, content, flags=re.DOTALL)

    def convert_mermaid_to_image(self, mermaid_code: str) -> Optional[str]:
        """Convert mermaid code to PNG image using mermaid-cli."""
        try:
            # Create unique filename based on content
            code_hash = hashlib.md5(mermaid_code.encode()).hexdigest()[:10]
            img_name = f"diagram_{code_hash}.png"
            img_path = os.path.join(self.image_output_dir, img_name)

            # Skip if already exists
            if os.path.exists(img_path):
                return img_path

            # Write temp mermaid file
            temp_file = "/tmp/mermaid_temp.mmd"
            with open(temp_file, 'w') as f:
                f.write(mermaid_code)

            # Run mermaid-cli
            result = subprocess.run(
                ["mmdc", "-i", temp_file, "-o", img_path, "-b", "white"],
                capture_output=True,
                text=True
            )

            if result.returncode == 0 and os.path.exists(img_path):
                return img_path
            else:
                print(f"Mermaid conversion failed: {result.stderr}")
                return None

        except FileNotFoundError:
            print("mermaid-cli not found. Install with: npm install -g @mermaid-js/mermaid-cli")
            return None

    def replace_mermaid_with_images(self, content: str) -> tuple[str, list[str]]:
        """Replace mermaid blocks with image placeholders."""
        pattern = r'```mermaid\n(.*?)\n```'
        image_paths = []

        def replacer(match):
            mermaid_code = match.group(1)
            img_path = self.convert_mermaid_to_image(mermaid_code)

            if img_path:
                image_paths.append(img_path)
                # Placeholder - will be replaced with WordPress URL after upload
                return f'{{{{IMAGE:{img_path}}}}}'
            else:
                # Fallback to shortcode if image conversion fails
                return f'[mermaid]\n{mermaid_code}\n[/mermaid]'

        converted = re.sub(pattern, replacer, content, flags=re.DOTALL)
        return converted, image_paths

    def convert_code_blocks(self, content: str) -> str:
        """Convert code blocks to WordPress shortcodes (SyntaxHighlighter Evolved)."""
        # Python code blocks
        content = re.sub(
            r'```python\n(.*?)\n```',
            r'[code language="python"]\n\1\n[/code]',
            content,
            flags=re.DOTALL
        )

        # Bash code blocks
        content = re.sub(
            r'```bash\n(.*?)\n```',
            r'[code language="bash"]\n\1\n[/code]',
            content,
            flags=re.DOTALL
        )

        # YAML code blocks
        content = re.sub(
            r'```ya?ml\n(.*?)\n```',
            r'[code language="yaml"]\n\1\n[/code]',
            content,
            flags=re.DOTALL
        )

        # JSON code blocks
        content = re.sub(
            r'```json\n(.*?)\n```',
            r'[code language="javascript"]\n\1\n[/code]',
            content,
            flags=re.DOTALL
        )

        # Generic code blocks (txt, dockerfile, etc.)
        content = re.sub(
            r'```\w*\n(.*?)\n```',
            r'[code]\n\1\n[/code]',
            content,
            flags=re.DOTALL
        )

        return content

    def extract_title(self, content: str) -> str:
        """Extract title from first H1 heading."""
        match = re.search(r'^# (.+)$', content, re.MULTILINE)
        return match.group(1) if match else "Untitled"

    def convert(self, content: str) -> tuple[str, str, list[str]]:
        """
        Convert markdown content to WordPress-ready HTML.

        Returns:
            tuple: (title, html_content, list_of_image_paths)
        """
        title = self.extract_title(content)
        image_paths = []

        # Handle mermaid diagrams
        if self.options.convert_mermaid_to_images:
            content, image_paths = self.replace_mermaid_with_images(content)
        else:
            content = self.convert_mermaid_to_shortcode(content)

        # Handle code blocks
        content = self.convert_code_blocks(content)

        # Convert remaining markdown to HTML
        html = markdown.markdown(
            content,
            extensions=['tables', 'fenced_code', 'toc', 'nl2br']
        )

        return title, html, image_paths


class WordPressPublisher:
    """Publish content to WordPress."""

    def __init__(self, config: WordPressConfig, options: PublishOptions):
        self.config = config
        self.options = options
        self.client = Client(config.xmlrpc_url, config.username, config.password)
        self.converter = MarkdownConverter(options)

    def upload_image(self, image_path: str) -> Optional[str]:
        """Upload image to WordPress and return URL."""
        try:
            with open(image_path, 'rb') as f:
                data = {
                    'name': os.path.basename(image_path),
                    'type': 'image/png',
                    'bits': f.read()
                }

            response = self.client.call(UploadFile(data))
            return response['url']
        except Exception as e:
            print(f"Failed to upload image {image_path}: {e}")
            return None

    def publish_post(self, title: str, content: str, category: str, image_paths: list[str] = None) -> Optional[int]:
        """Publish a single post to WordPress."""
        try:
            # Upload images and replace placeholders
            if image_paths:
                for img_path in image_paths:
                    img_url = self.upload_image(img_path)
                    if img_url:
                        placeholder = f'{{{{IMAGE:{img_path}}}}}'
                        img_tag = f'<img src="{img_url}" alt="Diagram" class="mermaid-diagram" />'
                        content = content.replace(placeholder, img_tag)

            # Create post
            post = WordPressPost()
            post.title = title
            post.content = content
            post.post_status = self.options.post_status
            post.terms_names = {
                'category': [self.options.base_category, category]
            }

            post_id = self.client.call(NewPost(post))
            print(f"Published: {title} (ID: {post_id})")
            return post_id

        except Exception as e:
            print(f"Failed to publish '{title}': {e}")
            return None

    def publish_file(self, filepath: str, category: str) -> Optional[int]:
        """Publish a single markdown file."""
        with open(filepath, 'r') as f:
            content = f.read()

        title, html, image_paths = self.converter.convert(content)
        return self.publish_post(title, html, category, image_paths)

    def publish_curriculum(self, base_path: str):
        """Publish all curriculum files from the notes directory."""
        base_path = Path(base_path)

        # Track statistics
        published = 0
        failed = 0

        # Walk through directory structure
        for month_dir in sorted(base_path.glob("Month_*")):
            month_name = month_dir.name.replace("_", " ")

            for week_dir in sorted(month_dir.glob("Week_*")):
                week_name = week_dir.name.replace("_", " ")
                category = f"{month_name} - {week_name}"

                for md_file in sorted(week_dir.glob("*.md")):
                    if md_file.name == "index.md":
                        continue

                    print(f"\nProcessing: {md_file}")
                    result = self.publish_file(str(md_file), category)

                    if result:
                        published += 1
                    else:
                        failed += 1

        print(f"\n{'='*50}")
        print(f"Publishing complete!")
        print(f"Published: {published}")
        print(f"Failed: {failed}")


def main():
    parser = argparse.ArgumentParser(
        description="Publish AI Curriculum markdown files to WordPress"
    )
    parser.add_argument(
        "--url",
        required=True,
        help="WordPress site URL (e.g., https://yourblog.com)"
    )
    parser.add_argument(
        "--user",
        required=True,
        help="WordPress username"
    )
    parser.add_argument(
        "--password",
        required=True,
        help="WordPress Application Password"
    )
    parser.add_argument(
        "--path",
        default="/Users/akash/Personal/notes",
        help="Path to curriculum notes directory"
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Publish immediately (default is draft)"
    )
    parser.add_argument(
        "--mermaid-images",
        action="store_true",
        help="Convert mermaid diagrams to images instead of shortcodes"
    )
    parser.add_argument(
        "--single",
        help="Publish a single file instead of all files"
    )

    args = parser.parse_args()

    # Setup configuration
    config = WordPressConfig(
        url=args.url,
        username=args.user,
        password=args.password
    )

    options = PublishOptions(
        convert_mermaid_to_images=args.mermaid_images,
        post_status="publish" if args.publish else "draft"
    )

    # Create publisher
    publisher = WordPressPublisher(config, options)

    # Publish
    if args.single:
        publisher.publish_file(args.single, "Uncategorized")
    else:
        publisher.publish_curriculum(args.path)


if __name__ == "__main__":
    main()
