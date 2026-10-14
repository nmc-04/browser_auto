"""
Firebase Authentication Operations
"""

import os
import hashlib
import requests
from typing import Optional, Dict, Any, Tuple
from utils.logger import logger
from utils.helpers import current_iso_time, generate_id
from firebase.firebase_config import get_firestore_db, get_firebase_app
from firebase_admin import auth as admin_auth

# Local fallback user store for demo/offline when Firebase credentials are not yet added
_LOCAL_USERS_DB: Dict[str, Dict[str, Any]] = {}


def _hash_password(password: str) -> str:
    """Securely hash password for local verification."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def sign_up_user(email: str, password: str, name: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """
    Signs up a new user using Firebase Auth and records user profile in Firestore.
    Returns: (success: bool, user_profile: dict, message: str)
    """
    if not email or not password or len(password) < 6:
        return False, None, "Password must be at least 6 characters long."

    email = email.strip().lower()
    app = get_firebase_app()
    db = get_firestore_db()

    if app and db:
        try:
            # 1. Create user in Firebase Auth
            user_record = admin_auth.create_user(
                email=email,
                password=password,
                display_name=name
            )
            user_id = user_record.uid

            # 2. Save user profile in Firestore 'users' collection
            user_data = {
                "user_id": user_id,
                "name": name,
                "email": email,
                "created_at": current_iso_time(),
                "last_login": current_iso_time()
            }
            db.collection("users").document(user_id).set(user_data)
            logger.info(f"User signed up in Firebase Auth: {email} (UID: {user_id})")
            return True, user_data, "Account created successfully."

        except Exception as e:
            err_str = str(e)
            if "EMAIL_EXISTS" in err_str or "email already exists" in err_str.lower():
                return False, None, "An account with this email already exists."
            logger.error(f"Firebase signup error: {e}")
            return False, None, f"Signup failed: {err_str}"

    # Fallback to local user store if Firebase is not yet configured
    if email in _LOCAL_USERS_DB:
        return False, None, "User already exists in local store."

    user_id = generate_id("usr")
    user_data = {
        "user_id": user_id,
        "name": name,
        "email": email,
        "password_hash": _hash_password(password),
        "created_at": current_iso_time(),
        "last_login": current_iso_time()
    }
    _LOCAL_USERS_DB[email] = user_data
    logger.info(f"User signed up (local mode): {email}")
    return True, {k: v for k, v in user_data.items() if k != "password_hash"}, "Account created (Local mode - Firebase not configured)."


def sign_in_user(email: str, password: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """
    Signs in a user and returns their user profile.
    Returns: (success: bool, user_profile: dict, message: str)
    """
    if not email or not password:
        return False, None, "Please provide email and password."

    email = email.strip().lower()
    app = get_firebase_app()
    db = get_firestore_db()
    web_api_key = os.getenv("FIREBASE_WEB_API_KEY", "")

    # If Firebase Web API Key is provided, use Google Identity Toolkit REST API
    if web_api_key:
        try:
            url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={web_api_key}"
            resp = requests.post(url, json={"email": email, "password": password, "returnSecureToken": True}, timeout=10)
            data = resp.json()
            if resp.status_code == 200:
                user_id = data["localId"]
                # Update last login in Firestore
                if db:
                    doc_ref = db.collection("users").document(user_id)
                    doc = doc_ref.get()
                    if doc.exists:
                        doc_ref.update({"last_login": current_iso_time()})
                        user_data = doc.to_dict()
                    else:
                        user_data = {
                            "user_id": user_id,
                            "name": data.get("displayName", email.split("@")[0]),
                            "email": email,
                            "created_at": current_iso_time(),
                            "last_login": current_iso_time()
                        }
                        doc_ref.set(user_data)
                else:
                    user_data = {"user_id": user_id, "name": email.split("@")[0], "email": email}

                logger.info(f"User authenticated via Firebase Auth REST: {email}")
                return True, user_data, "Login successful."
            else:
                err = data.get("error", {}).get("message", "Invalid credentials.")
                return False, None, f"Login failed: {err}"
        except Exception as e:
            logger.error(f"Firebase REST login error: {e}")

    # Verify directly against Firebase Auth using Admin SDK
    if app:
        try:
            user_record = admin_auth.get_user_by_email(email)
            if user_record:
                user_id = user_record.uid
                name = user_record.display_name or email.split("@")[0]
                user_data = {
                    "user_id": user_id,
                    "name": name,
                    "email": email,
                    "last_login": current_iso_time()
                }
                if db:
                    doc_ref = db.collection("users").document(user_id)
                    doc = doc_ref.get()
                    if doc.exists:
                        doc_ref.update({"last_login": current_iso_time()})
                        user_data = doc.to_dict()
                    else:
                        user_data["created_at"] = current_iso_time()
                        doc_ref.set(user_data)

                logger.info(f"User authenticated via Firebase Auth: {email} (UID: {user_id})")
                return True, user_data, "Login successful."
        except admin_auth.UserNotFoundError:
            return False, None, "User not found in Firebase Authentication. Please sign up."
        except Exception as e:
            logger.error(f"Firebase Admin user lookup error: {e}")

    # Fallback to local user store
    if email in _LOCAL_USERS_DB:
        user_record = _LOCAL_USERS_DB[email]
        if user_record.get("password_hash") == _hash_password(password):
            user_record["last_login"] = current_iso_time()
            return True, {k: v for k, v in user_record.items() if k != "password_hash"}, "Login successful."
        return False, None, "Invalid password."

    return False, None, "User not found. Please sign up."
