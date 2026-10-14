"""
Firebase Storage Operations for Browser Screenshots
Supports Firebase Storage buckets or direct Base64 encoding into Firestore documents.
"""

import os
import base64
from typing import Optional
from firebase.firebase_config import get_storage_bucket
from utils.logger import logger


def upload_screenshot(local_file_path: str, user_id: str, execution_id: str) -> str:
    """
    Uploads a screenshot to Firebase Storage if bucket is configured.
    Otherwise, encodes the screenshot into a Base64 Data URL so the image itself
    is stored directly in the Cloud Firestore document without needing Blaze/Storage!
    """
    if not os.path.exists(local_file_path):
        return ""

    bucket = get_storage_bucket()
    file_name = os.path.basename(local_file_path)

    # 1. If Firebase Storage Bucket is configured and active, upload to bucket
    if bucket:
        storage_path = f"users/{user_id}/executions/{execution_id}/{file_name}"
        try:
            blob = bucket.blob(storage_path)
            blob.upload_from_filename(local_file_path)
            blob.make_public()
            logger.info(f"Screenshot uploaded to Firebase Storage: {storage_path}")
            return blob.public_url
        except Exception as e:
            logger.warning(f"Firebase Storage upload failed: {e}. Falling back to Base64 Firestore storage.")

    # 2. Cloud Firestore Base64 Storage (No credit card / Blaze plan required!)
    try:
        with open(local_file_path, "rb") as img_file:
            encoded_bytes = base64.b64encode(img_file.read()).decode("utf-8")
            data_url = f"data:image/png;base64,{encoded_bytes}"
            logger.info(f"Stored screenshot directly in Firestore as Base64 image ({file_name})")
            return data_url
    except Exception as e:
        logger.error(f"Error encoding screenshot to Base64: {e}")
        return local_file_path
