"""
Firebase Configuration and Admin SDK Initialization
"""

import os
import json
from typing import Optional, Tuple
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore, storage, auth
from utils.logger import logger

load_dotenv(override=True)

_firebase_app: Optional[firebase_admin.App] = None
_firestore_db = None
_storage_bucket = None


def is_firebase_configured() -> bool:
    """Checks whether Firebase credentials or service account are provided."""
    if os.getenv("FIREBASE_ENABLED", "true").strip().lower() in {"0", "false", "no", "off"}:
        return False
    service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "")
    if service_account_path and os.path.exists(service_account_path):
        return True
    if os.getenv("FIREBASE_PROJECT_ID") and os.getenv("FIREBASE_PRIVATE_KEY"):
        return True
    return False


def get_firebase_app() -> Optional[firebase_admin.App]:
    """Initializes and returns the singleton Firebase Admin App."""
    global _firebase_app, _firestore_db, _storage_bucket

    if _firebase_app is not None:
        return _firebase_app

    # Reuse existing default app if already initialized in Python runtime
    try:
        _firebase_app = firebase_admin.get_app()
        return _firebase_app
    except (ValueError, Exception):
        pass

    if not is_firebase_configured():
        return None

    try:
        service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "")
        storage_bucket_name = os.getenv("FIREBASE_STORAGE_BUCKET", "")

        options = {}
        if storage_bucket_name:
            options["storageBucket"] = storage_bucket_name

        if service_account_path and os.path.exists(service_account_path):
            cred = credentials.Certificate(service_account_path)
            _firebase_app = firebase_admin.initialize_app(cred, options)
            logger.info(f"Firebase initialized from service account: {service_account_path}")
        elif os.getenv("FIREBASE_PROJECT_ID") and os.getenv("FIREBASE_PRIVATE_KEY"):
            private_key = os.getenv("FIREBASE_PRIVATE_KEY", "").replace("\\n", "\n")
            cred_dict = {
                "type": "service_account",
                "project_id": os.getenv("FIREBASE_PROJECT_ID"),
                "private_key": private_key,
                "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
                "token_uri": "https://oauth2.googleapis.com/token",
            }
            cred = credentials.Certificate(cred_dict)
            _firebase_app = firebase_admin.initialize_app(cred, options)
            logger.info("Firebase initialized from environment credentials.")

        return _firebase_app
    except Exception as e:
        logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
        return None


def get_firestore_db():
    """Returns Firestore client if available, else None."""
    global _firestore_db
    if _firestore_db is not None:
        return _firestore_db

    app = get_firebase_app()
    if app:
        try:
            _firestore_db = firestore.client()
            return _firestore_db
        except Exception as e:
            logger.error(f"Failed to get Firestore client: {e}")
            return None
    return None


def get_storage_bucket():
    """Returns Firebase Storage bucket if available, else None."""
    global _storage_bucket
    if _storage_bucket is not None:
        return _storage_bucket

    app = get_firebase_app()
    if app:
        try:
            _storage_bucket = storage.bucket()
            return _storage_bucket
        except Exception as e:
            logger.error(f"Failed to get Storage bucket: {e}")
            return None
    return None
