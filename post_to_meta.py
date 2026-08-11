"""
Posts today's Daily Manna graphic + caption to Facebook and Instagram.

Facebook: uploads the image file directly to the Page.
Instagram: requires a public image URL (it can't accept a raw file upload),
so this expects you to pass the raw.githubusercontent.com URL of the image
after it's been committed to the repo by the GitHub Actions workflow.

Requires one environment variable:
    PAGE_ACCESS_TOKEN   -- the permanent Page access token you generated

Usage:
    python post_to_meta.py path/to/output.png "caption text" "https://raw.githubusercontent.com/.../output.png"
"""

import os
import sys
import requests

PAGE_ID = "1169129646275057"
IG_BUSINESS_ID = "17841416232075414"
GRAPH_VERSION = "v26.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"


def post_to_facebook(image_path: str, caption: str, page_access_token: str) -> dict:
    """Uploads the image file directly to the Facebook Page, published immediately."""
    url = f"{GRAPH_BASE}/{PAGE_ID}/photos"
    with open(image_path, "rb") as f:
        response = requests.post(
            url,
            data={"caption": caption, "access_token": page_access_token},
            files={"source": f},
        )
    response.raise_for_status()
    return response.json()


def post_to_instagram(image_public_url: str, caption: str, page_access_token: str) -> dict:
    """Two-step Instagram publish: create a media container, then publish it."""
    # Step 1: create the media container
    container_url = f"{GRAPH_BASE}/{IG_BUSINESS_ID}/media"
    container_resp = requests.post(
        container_url,
        data={
            "image_url": image_public_url,
            "caption": caption,
            "access_token": page_access_token,
        },
    )
    container_resp.raise_for_status()
    creation_id = container_resp.json()["id"]

    # Step 2: publish the container
    publish_url = f"{GRAPH_BASE}/{IG_BUSINESS_ID}/media_publish"
    publish_resp = requests.post(
        publish_url,
        data={"creation_id": creation_id, "access_token": page_access_token},
    )
    publish_resp.raise_for_status()
    return publish_resp.json()


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python post_to_meta.py <image_path> <caption> <public_image_url>")
        sys.exit(1)

    image_path, caption, image_public_url = sys.argv[1], sys.argv[2], sys.argv[3]

    token = os.environ.get("PAGE_ACCESS_TOKEN")
    if not token:
        print("ERROR: Set the PAGE_ACCESS_TOKEN environment variable first.")
        sys.exit(1)

    print("Posting to Facebook...")
    fb_result = post_to_facebook(image_path, caption, token)
    print("Facebook result:", fb_result)

    print("Posting to Instagram...")
    ig_result = post_to_instagram(image_public_url, caption, token)
    print("Instagram result:", ig_result)
