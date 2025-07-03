# Marketing Studio - Enhanced Agent

A comprehensive content marketing agent that can write and post content to LinkedIn, Twitter, and YouTube.

## Features

### Content Generation
- **LinkedIn Posts**: Generate engaging LinkedIn content with AI
- **Twitter Posts**: Create viral Twitter threads and posts
- **YouTube Descriptions**: Write SEO-optimized YouTube video descriptions

### Automated Posting
- **LinkedIn Automation**: Automatically post content to LinkedIn using Selenium
- **LinkedIn Scheduling**: Schedule posts for specific dates and times
- **YouTube Upload**: Upload videos to YouTube with metadata

### Content Management
- **Supabase Integration**: Store and retrieve past content for context
- **State Management**: Maintain conversation state and content history

## Setup

### Prerequisites

1. **Python Dependencies**
   ```bash
   pip install langchain-openai langgraph supabase selenium webdriver-manager python-dotenv google-auth-oauthlib google-api-python-client
   ```

2. **Environment Variables**
   ```bash
   # Required
   OPENAI_API_KEY=your_openai_api_key
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_key
   
   # For LinkedIn posting
   LINKEDIN_EMAIL=your_linkedin_email
   LINKEDIN_PASSWORD=your_linkedin_password
   
   # For YouTube uploads
   # You'll need to set up Google OAuth (see YouTube Setup section)
   ```

### LinkedIn Setup

1. Set your LinkedIn credentials in environment variables:
   ```bash
   export LINKEDIN_EMAIL="your_email@example.com"
   export LINKEDIN_PASSWORD="your_password"
   ```

2. The agent will automatically use these credentials to post content.

3. **Browser Cache Persistence**: The LinkedIn automation now saves browser cache and cookies, so you don't need to login every time:
   - Browser data is stored in `linkedin_browser_data/` directory (same location as the script)
   - Subsequent runs will skip the login process if the session is still valid

4. **Scheduling Posts**: You can schedule posts by providing a `schedule_time` parameter in ISO format:
   - Format: `YYYY-MM-DDTHH:MM:SS` (e.g., `2024-01-15T10:30:00`)
   - Timezone: Use your local timezone or UTC
   - Example: `2024-01-15T10:30:00+00:00` for UTC

### YouTube Setup

1. **Create Google Cloud Project**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing one
   - Enable YouTube Data API v3

2. **Create OAuth Credentials**
   - Go to APIs & Services > Credentials
   - Create OAuth 2.0 Client ID
   - Download the JSON file as `client_secret.json`
   - Place it in your project root

3. **First Run Authentication**
   - Run the YouTube upload script once to authenticate
   - A browser window will open for Google OAuth
   - Complete the authentication process
   - Credentials will be saved in `token.pickle`

## Usage

### Basic Usage

```python
from agent import graph

# Create a message
result = graph.invoke({
    "messages": [
        {
            "role": "user",
            "content": "Write a LinkedIn post about Davia's AI features for developers"
        }
    ]
})

print(result["messages"][-1].content)
```

### Advanced Usage

```python
# Write and post to LinkedIn
result = graph.invoke({
    "messages": [
        {
            "role": "user", 
            "content": "Write and post a LinkedIn post about our new AI features. Target audience: developers and entrepreneurs."
        }
    ]
})

# Upload video to YouTube
result = graph.invoke({
    "messages": [
        {
            "role": "user",
            "content": "Upload the video at /path/to/video.mp4 to YouTube with title 'Davia AI Demo' and description 'Learn how Davia helps build AI apps'"
        }
    ]
})
```

### Testing

Run the test script to verify everything works:

```bash
python test_agent.py
```

### Cache Persistence Demo

Test the browser cache functionality:

```bash
# Run the cache demo (will login first time)
python linkedin_cache_example.py

# Run again to see cache in action (should skip login)
python linkedin_cache_example.py
```

## Tools Available

### Content Generation Tools
- `write_linkedin_post`: Generate LinkedIn post content
- `write_twitter_post`: Generate Twitter post content
- `write_youtube_description`: Generate YouTube video descriptions

### Automation Tools
- `post_to_linkedin`: Actually post content to LinkedIn (can schedule posts, requires credentials)
- `upload_to_youtube`: Upload videos to YouTube (requires OAuth setup)

## Agent Capabilities

The agent can:

1. **Generate Content**: Write engaging posts for different platforms
2. **Learn from History**: Use past posts as context for new content
3. **Automate Posting**: Actually post content to LinkedIn
4. **Schedule Posts**: Schedule LinkedIn posts for specific dates and times
5. **Upload Videos**: Upload videos to YouTube with proper metadata
6. **Manage State**: Keep track of all generated content in Supabase

## Example Prompts

### Content Generation
```
"Write a LinkedIn post about Davia's new AI features for building frontend applications. Target audience: developers and entrepreneurs."
```

### Automated Posting
```
"Write and post a LinkedIn post about our latest product update. Make it public visibility."
```

### Scheduled Posting
```
"Write and schedule a LinkedIn post about our new feature for tomorrow at 10 AM."
```

### YouTube Upload
```
"Upload the demo video at /videos/demo.mp4 to YouTube with title 'Davia AI Demo' and schedule it for tomorrow at 10 AM."
```

## Troubleshooting

### LinkedIn Issues
- Ensure `LINKEDIN_EMAIL` and `LINKEDIN_PASSWORD` are set correctly
- LinkedIn may require 2FA - consider using app passwords
- The Selenium automation runs in headless mode by default

### YouTube Issues
- Ensure `client_secret.json` is in the project root
- Complete the OAuth flow on first run
- Check that the video file path is correct and accessible

### General Issues
- Verify all environment variables are set
- Check that Supabase tables exist and are accessible
- Ensure all Python dependencies are installed

## Security Notes

- Store credentials securely using environment variables
- Never commit `client_secret.json` or `token.pickle` to version control
- Use app passwords for LinkedIn if 2FA is enabled
- Consider using a dedicated Google account for YouTube uploads

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License.