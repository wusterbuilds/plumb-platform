"""One-time OAuth2 setup for Gmail API.

Run this once to authorize the application:
    python -m app.email.auth_setup

This opens a browser, you log into the Gmail account, grant permissions,
and a token.json file is saved for future use.
"""

from app.email.client import get_gmail_service


def main():
    print("Setting up Gmail OAuth2 credentials...")
    print("A browser window will open. Log into the Gmail account you want to use.")
    print()

    service = get_gmail_service()

    # Verify access by fetching profile
    profile = service.users().getProfile(userId="me").execute()
    print(f"Authenticated as: {profile['emailAddress']}")
    print(f"Token saved. You can now enable GMAIL_ENABLED=true in .env")


if __name__ == "__main__":
    main()
