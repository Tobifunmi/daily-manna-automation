"""
Posts today's Daily Manna graphic + caption to Facebook and Instagram,
including Stories on both platforms.

Facebook: uploads the image file directly.
Instagram: requires a public image URL (can't accept a raw file upload) --
this expects the jsDelivr URL pinned to the day's commit SHA.

Requires one environment variable:
    PAGE_ACCESS_TOKEN   -- the permanent Page access token you generated
"""

import os
import sys
import time
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
    if response.status_code != 200:
        raise RuntimeError(f"Facebook post failed: {response.text}")
    return response.json()


def post_to_instagram(image_public_url: str, caption: str, page_access_token: str) -> dict:
    """Two-step Instagram publish: create a media container, wait for it to
    finish processing, then publish it. Retries transient failures at each
    step and surfaces Meta's actual error message if anything fails."""

    # Step 1: create the media container (retried -- "media could not be
    # fetched" errors are often just a transient CDN timing issue)
    container_url = f"{GRAPH_BASE}/{IG_BUSINESS_ID}/media"
    creation_id = None
    last_error = None
    for attempt in range(4):
        container_resp = requests.post(
            container_url,
            data={
                "image_url": image_public_url,
                "caption": caption,
                "access_token": page_access_token,
            },
        )
        if container_resp.status_code == 200:
            creation_id = container_resp.json()["id"]
            break
        last_error = container_resp.text
        print(f"Container creation attempt {attempt + 1} failed, retrying in 10s: {last_error}")
        time.sleep(10)

    if creation_id is None:
        raise RuntimeError(f"Instagram container creation failed after retries: {last_error}")

    # Step 2: poll until Instagram has actually finished fetching/processing the image
    status_url = f"{GRAPH_BASE}/{creation_id}"
    status_code = None
    for attempt in range(15):  # up to ~75 seconds
        status_resp = requests.get(
            status_url,
            params={"fields": "status_code", "access_token": page_access_token},
        )
        status_code = status_resp.json().get("status_code")
        if status_code == "FINISHED":
            break
        if status_code == "ERROR":
            raise RuntimeError(f"Instagram failed to process the image: {status_resp.text}")
        time.sleep(5)
    else:
        raise RuntimeError(
            f"Instagram container never finished processing (last status: {status_code})"
        )

    # Step 3: publish the container (retried -- "Media Not Found" right after
    # a FINISHED status is a known transient Instagram API quirk)
    publish_url = f"{GRAPH_BASE}/{IG_BUSINESS_ID}/media_publish"
    last_error = None
    for attempt in range(4):
        publish_resp = requests.post(
            publish_url,
            data={"creation_id": creation_id, "access_token": page_access_token},
        )
        if publish_resp.status_code == 200:
            return publish_resp.json()
        last_error = publish_resp.text
        print(f"Publish attempt {attempt + 1} failed, retrying in 10s: {last_error}")
        time.sleep(10)

    raise RuntimeError(f"Instagram publish failed after retries: {last_error}")


def post_to_facebook_story(image_path: str, page_access_token: str) -> dict:
    """Facebook Stories are a two-step process: upload the photo unpublished,
    then attach that photo to a story."""
    upload_url = f"{GRAPH_BASE}/{PAGE_ID}/photos"
    with open(image_path, "rb") as f:
        upload_resp = requests.post(
            upload_url,
            data={"published": "false", "access_token": page_access_token},
            files={"source": f},
        )
    if upload_resp.status_code != 200:
        raise RuntimeError(f"Facebook story photo upload failed: {upload_resp.text}")
    photo_id = upload_resp.json()["id"]

    story_url = f"{GRAPH_BASE}/{PAGE_ID}/photo_stories"
    story_resp = requests.post(
        story_url,
        data={"photo_id": photo_id, "access_token": page_access_token},
    )
    if story_resp.status_code != 200:
        raise RuntimeError(f"Facebook story publish failed: {story_resp.text}")
    return story_resp.json()


def post_to_instagram_story(image_public_url: str, page_access_token: str) -> dict:
    """Instagram Stories use the same container flow as a regular post,
    just with media_type=STORIES and no caption. Retries transient
    failures at container creation, status polling, and publish."""

    container_url = f"{GRAPH_BASE}/{IG_BUSINESS_ID}/media"
    creation_id = None
    last_error = None
    for attempt in range(4):
        container_resp = requests.post(
            container_url,
            data={
                "image_url": image_public_url,
                "media_type": "STORIES",
                "access_token": page_access_token,
            },
        )
        if container_resp.status_code == 200:
            creation_id = container_resp.json()["id"]
            break
        last_error = container_resp.text
        print(f"Story container creation attempt {attempt + 1} failed, retrying in 10s: {last_error}")
        time.sleep(10)

    if creation_id is None:
        raise RuntimeError(f"Instagram story container creation failed after retries: {last_error}")

    status_url = f"{GRAPH_BASE}/{creation_id}"
    status_code = None
    for attempt in range(15):
        status_resp = requests.get(
            status_url,
            params={"fields": "status_code", "access_token": page_access_token},
        )
        status_code = status_resp.json().get("status_code")
        if status_code == "FINISHED":
            break
        if status_code == "ERROR":
            raise RuntimeError(f"Instagram story failed to process: {status_resp.text}")
        time.sleep(5)
    else:
        raise RuntimeError(
            f"Instagram story container never finished processing (last status: {status_code})"
        )

    # Extra buffer: give Meta's backend a moment to fully register the
    # container as FINISHED before we try to publish it -- this is the
    # specific gap that caused the "Media Not Found" failure.
    time.sleep(5)

    publish_url = f"{GRAPH_BASE}/{IG_BUSINESS_ID}/media_publish"
    last_error = None
    for attempt in range(4):
        publish_resp = requests.post(
            publish_url,
            data={"creation_id": creation_id, "access_token": page_access_token},
        )
        if publish_resp.status_code == 200:
            return publish_resp.json()
        last_error = publish_resp.text
        print(f"Story publish attempt {attempt + 1} failed, retrying in 10s: {last_error}")
        time.sleep(10)

    raise RuntimeError(f"Instagram story publish failed after retries: {last_error}")


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
