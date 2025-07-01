import os
from typing import Any
from urllib.parse import urlencode

import requests


class LinkedInPoster:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str = "http://localhost",
    ):
        """
        Initialize LinkedIn Poster with OAuth credentials.

        Args:
            client_id: LinkedIn app client ID
            client_secret: LinkedIn app client secret
            redirect_uri: OAuth redirect URI (default: localhost for testing)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.access_token = None
        self.person_urn = None

    def authenticate(self) -> bool:
        """
        Authenticate with LinkedIn using OAuth 2.0.
        Returns True if authentication successful, False otherwise.
        """
        # Step 1: Generate authorization URL
        auth_url = "https://www.linkedin.com/oauth/v2/authorization"
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": "w_member_social",
            "state": "random_state_string",
        }

        auth_url_with_params = f"{auth_url}?{urlencode(params)}"

        print("Please visit this URL to authorize the application:")
        print(auth_url_with_params)
        print(
            "\nAfter authorization, you'll be redirected to a URL that may show an error page."
            "\nThis is normal - just copy the 'code' parameter from the URL in your browser's address bar."
            "\nThe URL will look like: http://localhost?code=AQT...&state=random_state_string"
            "\n\n⚠️  IMPORTANT: Each authorization code can only be used once!"
            "\n   If you get an error, you'll need to visit the authorization URL again to get a fresh code."
        )

        # For testing purposes, we'll use a simple input method
        # In production, you'd want to set up a proper web server to handle the callback
        authorization_code = input(
            "Enter the authorization code from the redirect URL: "
        ).strip()

        if not authorization_code:
            print("No authorization code provided.")
            return False

        # Step 2: Exchange authorization code for access token
        token_url = "https://www.linkedin.com/oauth/v2/accessToken"
        token_data = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
        }

        try:
            print(f"Debug: Making token request to {token_url}")
            print(f"Debug: Client ID: {self.client_id}")
            print(f"Debug: Redirect URI: {self.redirect_uri}")
            print(f"Debug: Authorization code length: {len(authorization_code)}")

            response = requests.post(token_url, data=token_data)

            if response.status_code != 200:
                print(f"Debug: Response status: {response.status_code}")
                print(f"Debug: Response content: {response.text}")
                response.raise_for_status()

            token_info = response.json()

            self.access_token = token_info.get("access_token")
            if not self.access_token:
                print("Failed to get access token.")
                return False

            print("Successfully obtained access token!")

            # Step 3: Get user profile to get Person URN
            return self._get_person_urn()

        except requests.exceptions.RequestException as e:
            print(f"Error during token exchange: {e}")
            return False

    def _get_person_urn(self) -> bool:
        """
        Get the Person URN for the authenticated user.
        Since we only have w_member_social scope, we'll use a different approach.
        Returns True if successful, False otherwise.
        """
        if not self.access_token:
            print("No access token available.")
            return False

        # Try multiple endpoints to get the Person URN
        endpoints = [
            "https://api.linkedin.com/v2/me",
            "https://api.linkedin.com/v2/me?projection=(id,firstName,lastName)",
            "https://api.linkedin.com/v2/me?projection=(id)",
        ]

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
        }

        for endpoint in endpoints:
            try:
                print(f"Trying endpoint: {endpoint}")
                response = requests.get(endpoint, headers=headers)
                print(f"Response status: {response.status_code}")

                if response.status_code == 200:
                    profile_data = response.json()
                    user_id = profile_data.get("id")
                    if user_id:
                        # Try both formats
                        self.person_urn = f"urn:li:member:{user_id}"
                        print(f"✅ Successfully obtained Person URN: {self.person_urn}")
                        return True
                elif response.status_code == 403:
                    print(f"403 Forbidden for {endpoint} - trying next endpoint...")
                    continue
                else:
                    print(f"Unexpected status {response.status_code} for {endpoint}")

            except requests.exceptions.RequestException as e:
                print(f"Error with {endpoint}: {e}")
                continue

        print("All profile endpoints failed. Trying to extract from access token...")

        # Try to extract user ID from the access token
        if self._extract_user_id_from_token():
            return True

        return self._get_person_urn_from_user()

    def _extract_user_id_from_token(self) -> bool:
        """
        Try to extract user ID from the access token by making a test post request.
        """
        print("Attempting to extract user ID from access token...")

        # Make a minimal test request to see what error we get
        test_url = "https://api.linkedin.com/v2/ugcPosts"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }

        # Use a dummy Person URN to see what the error message tells us
        test_data = {
            "author": "urn:li:member:123456789",  # Dummy ID
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": "test"},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "CONNECTIONS"},
        }

        try:
            response = requests.post(test_url, headers=headers, json=test_data)
            print(f"Test request status: {response.status_code}")
            print(f"Test response: {response.text}")

            # If we get a 403 with specific error about the author, we can extract info
            if response.status_code == 403:
                error_text = response.text
                if "author" in error_text.lower():
                    print(
                        "Got author-related error. This suggests the token is valid but Person URN is wrong."
                    )
                    return False

        except Exception as e:
            print(f"Error in test request: {e}")

        return False

    def _get_person_urn_from_user(self) -> bool:
        """
        Alternative method to get Person URN by asking the user.
        This is needed when we don't have r_liteprofile permission.
        """
        print("\n⚠️  Unable to automatically get your LinkedIn Person URN.")
        print("You'll need to provide it manually.")
        print("\nTo find your Person URN:")
        print("1. Go to your LinkedIn profile")
        print(
            "2. Look at the URL - it should be like: https://www.linkedin.com/in/your-profile-id/"
        )
        print("3. But you need the NUMERIC ID, not the profile slug")
        print(
            "4. You can find this in your LinkedIn settings or by using a LinkedIn ID finder"
        )
        print(
            "\nYour Person URN format should be: urn:li:member:123456789 (numeric ID only)"
        )
        print("\nNote: LinkedIn expects 'urn:li:member:' format, not 'urn:li:person:'")

        person_urn = input("Enter your Person URN (urn:li:person:...): ").strip()

        if person_urn.startswith("urn:li:person:") or person_urn.startswith(
            "urn:li:member:"
        ):
            self.person_urn = person_urn
            print(f"✅ Person URN set to: {self.person_urn}")
            return True
        else:
            print(
                "❌ Invalid Person URN format. It should start with 'urn:li:person:' or 'urn:li:member:'"
            )
            return False

    def post_text(self, text: str, visibility: str = "CONNECTIONS") -> str | None:
        """
        Post text content to LinkedIn.

        Args:
            text: The text content to post
            visibility: Post visibility - "CONNECTIONS" (private) or "PUBLIC"

        Returns:
            Post ID if successful, None otherwise
        """
        if not self.access_token or not self.person_urn:
            print("Not authenticated. Please call authenticate() first.")
            return None

        if visibility not in ["CONNECTIONS", "PUBLIC"]:
            print("Visibility must be 'CONNECTIONS' or 'PUBLIC'")
            return None

        post_url = "https://api.linkedin.com/v2/ugcPosts"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }

        post_data = {
            "author": self.person_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": visibility},
        }

        try:
            response = requests.post(post_url, headers=headers, json=post_data)
            response.raise_for_status()

            # Get the post ID from the response header
            post_id = response.headers.get("X-RestLi-Id")
            print(f"Successfully posted! Post ID: {post_id}")
            return post_id

        except requests.exceptions.RequestException as e:
            print(f"Error posting to LinkedIn: {e}")
            if hasattr(e, "response") and e.response is not None:
                print(f"Response content: {e.response.text}")
            return None

    def post_article(
        self,
        text: str,
        url: str,
        title: str = "",
        description: str = "",
        visibility: str = "CONNECTIONS",
    ) -> str | None:
        """
        Post an article/URL to LinkedIn.

        Args:
            text: The commentary text
            url: The URL to share
            title: Optional title for the article
            description: Optional description for the article
            visibility: Post visibility - "CONNECTIONS" (private) or "PUBLIC"

        Returns:
            Post ID if successful, None otherwise
        """
        if not self.access_token or not self.person_urn:
            print("Not authenticated. Please call authenticate() first.")
            return None

        if visibility not in ["CONNECTIONS", "PUBLIC"]:
            print("Visibility must be 'CONNECTIONS' or 'PUBLIC'")
            return None

        post_url = "https://api.linkedin.com/v2/ugcPosts"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }

        media_data: dict[str, Any] = {"status": "READY", "originalUrl": url}

        if title:
            media_data["title"] = {"text": title}
        if description:
            media_data["description"] = {"text": description}

        post_data = {
            "author": self.person_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "ARTICLE",
                    "media": [media_data],
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": visibility},
        }

        try:
            response = requests.post(post_url, headers=headers, json=post_data)
            response.raise_for_status()

            post_id = response.headers.get("X-RestLi-Id")
            print(f"Successfully posted article! Post ID: {post_id}")
            return post_id

        except requests.exceptions.RequestException as e:
            print(f"Error posting article to LinkedIn: {e}")
            if hasattr(e, "response") and e.response is not None:
                print(f"Response content: {e.response.text}")
            return None


def test_linkedin_posting():
    """
    Test function to demonstrate LinkedIn posting functionality.
    """
    # You'll need to get these from your LinkedIn app in the Developer Portal
    CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID")
    CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET")

    if not CLIENT_ID or not CLIENT_SECRET:
        print(
            "Please set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET environment variables."
        )
        print("You can get these from https://www.linkedin.com/developers/")
        return

    # Initialize the LinkedIn poster
    poster = LinkedInPoster(CLIENT_ID, CLIENT_SECRET)

    # Authenticate
    print("Starting LinkedIn authentication...")
    if not poster.authenticate():
        print("Authentication failed. Exiting.")
        return

    # Test posting a private text post (visible only to connections)
    print("\n--- Testing Private Text Post ---")
    test_text = (
        "This is a test post from my LinkedIn API integration! 🤖 #LinkedInAPI #Testing"
    )
    post_id = poster.post_text(test_text, visibility="CONNECTIONS")

    if post_id:
        print(f"✅ Private text post successful! Post ID: {post_id}")
    else:
        print("❌ Private text post failed!")

    # Test posting a public article
    print("\n--- Testing Public Article Post ---")
    article_text = "Check out this interesting article about LinkedIn API integration!"
    article_url = "https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/share-on-linkedin"
    article_title = "Share on LinkedIn - Microsoft Learn"
    article_description = (
        "Learn how to integrate LinkedIn sharing functionality into your applications."
    )

    article_post_id = poster.post_article(
        text=article_text,
        url=article_url,
        title=article_title,
        description=article_description,
        visibility="PUBLIC",
    )

    if article_post_id:
        print(f"✅ Public article post successful! Post ID: {article_post_id}")
    else:
        print("❌ Public article post failed!")


if __name__ == "__main__":
    test_linkedin_posting()
