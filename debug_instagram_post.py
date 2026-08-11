"""
Diagnostic version: shows the FULL response from Instagram's API at each
step, including the actual error message/code Meta sends back, instead of
just "400 Bad Request".

Usage:
    python debug_instagram_post.py "<public_image_url>"
"""

import os
import sys
import requests

IG_BUSINESS_ID = "17841416232075414"
GRAPH_VERSION = "v26.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"

token = os.environ["PAGE_ACCESS_TOKEN"]
image_url = sys.argv[1]

print("=== Step 1: creating media container ===")
container_resp = requests.post(
    f"{GRAPH_BASE}/{IG_BUSINESS_ID}/media",
    data={"image_url": image_url, "caption": "Diagnostic test", "access_token": token},
)
print("Status code:", container_resp.status_code)
print("Response:", container_resp.json())

if container_resp.status_code != 200:
    sys.exit("Container creation failed — see error above.")

creation_id = container_resp.json()["id"]

print("\n=== Step 2: checking container status ===")
status_resp = requests.get(
    f"{GRAPH_BASE}/{creation_id}",
    params={"fields": "status_code,status", "access_token": token},
)
print("Status code:", status_resp.status_code)
print("Response:", status_resp.json())

print("\n=== Step 3: publishing container ===")
publish_resp = requests.post(
    f"{GRAPH_BASE}/{IG_BUSINESS_ID}/media_publish",
    data={"creation_id": creation_id, "access_token": token},
)
print("Status code:", publish_resp.status_code)
print("Response:", publish_resp.json())
