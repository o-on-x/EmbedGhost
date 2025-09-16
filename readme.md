# Custom Post Embed Viewer

A privacy-focused app for embedding and displaying posts from X (Twitter), YouTube, and Rumble—including live streams—in private chats or community browsers.  
This project **never uses third-party embed scripts** (like YouTube iframe, Twitter's widget.js, etc), so your viewers avoid ad-tracking, fingerprinting, and leaking info to outside platforms.  
Streams play directly (via hls.js for live/HLS), and quote/reply chains are fully supported.

## Why Use This?

- **No tracker embeds**: Never loads third-party scripts—less surveillance, faster, and safer for private or community spaces.
- **Your data stays yours**: No cookies, cross-site requests, or browser fingerprinting from embedded social/video platforms.
- **Works anywhere**: Ideal for chat apps, private communities, or self-hosted feeds.

## Install & Run

1. Clone this repo.

2. Install dependencies:

uv pip install -r requirements.txt


3. Download the [yt-dlp binary](https://github.com/yt-dlp/yt-dlp/releases/latest) for your OS and put it in the project directory.  
Rename it to `yt-dlp`.

4. Start the server:

uv run python -m uvicorn backend:app --reload


5. Open your browser and go to [http://localhost:8000](http://localhost:8000).  
The app will serve `showpage.html` automatically.

## License

MIT
