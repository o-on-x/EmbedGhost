import os
import re
import uuid
import asyncio
import subprocess
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from twikit.guest import GuestClient

app = FastAPI()
MEDIA_DIR = "media"
YTDLP_BIN = os.path.join(os.path.dirname(__file__), "yt-dlp")  # Adjust path as needed
TMP_DIR = "/tmp"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")

def ensure_media_dir():
    if not os.path.exists(MEDIA_DIR):
        os.makedirs(MEDIA_DIR)

def sanitize_url(val):
    print(f"DEBUG: sanitize_url input type={type(val)}, value={val}")
    if isinstance(val, list):
        print(f"DEBUG: sanitize_url converted list to value = {val[0]}")
        return val[0]
    return val

def is_youtube_url(url):
    yt_pattern = r'(youtube\.com/watch\?v=|youtu\.be/)'
    match = re.search(yt_pattern, url.lower())
    print(f"DEBUG: is_youtube_url: {bool(match)} for url {url}")
    return match

def is_rumble_url(url):
    found = "rumble.com" in url.lower()
    print(f"DEBUG: is_rumble_url: {found} for url {url}")
    return found

def get_youtube_muxed_stream(youtube_url):
    try:
        print(f"DEBUG: Attempting yt-dlp muxed extraction for {youtube_url}")
        # Try to get direct muxed stream first (mp4/webm)
        result = subprocess.run([
            YTDLP_BIN, '-f', 'best[ext=mp4]/best',
            '--no-playlist', '-g', youtube_url
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        print(f"DEBUG: yt-dlp stdout={result.stdout}")
        urls = [line.strip() for line in result.stdout.strip().split('\n') if line.startswith('http')]
        print(f"DEBUG: yt-dlp (muxed) URLs: {urls}")
        if urls:
            print(f"DEBUG: Returning direct muxed stream: {urls[0]}")
            return urls[0], None
        # Fallback if no muxed stream: download/mux as temp file
        temp_name = f"ytmux-{uuid.uuid4().hex}.mp4"
        temp_out = os.path.join(TMP_DIR, temp_name)
        print(f"DEBUG: Attempting yt-dlp fallback mux to {temp_out}")
        merge_proc = subprocess.run([
            YTDLP_BIN, '-f', 'bestvideo+bestaudio/best',
            '--no-playlist', '--merge-output-format', 'mp4',
            '-o', temp_out, youtube_url
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        print(f"DEBUG: yt-dlp fallback merge returncode={merge_proc.returncode}")
        if os.path.exists(temp_out):
            print(f"DEBUG: yt-dlp created muxed file: {temp_out}")
            return None, temp_name
        print("DEBUG: Fallback mux failed, no file created.")
        return None, None
    except Exception as e:
        print(f"ERROR: yt-dlp failed for YouTube: {e}")
        return None, None

def get_rumble_stream_url(rumble_url):
    try:
        print(f"DEBUG: Attempting yt-dlp extraction for Rumble {rumble_url}")
        result = subprocess.run([YTDLP_BIN, '-g', rumble_url],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        print(f"DEBUG: yt-dlp stdout={result.stdout}")
        urls = [line.strip() for line in result.stdout.strip().split('\n') if line.startswith('http')]
        print(f"DEBUG: Rumble stream URLs: {urls}")
        return urls[0] if urls else None
    except Exception as e:
        print(f"ERROR: yt-dlp failed for Rumble: {e}")
        return None

def get_video_metadata(url):
    try:
        print(f"DEBUG: Attempting yt-dlp metadata extraction for {url}")
        result = subprocess.run(
            [YTDLP_BIN, '--skip-download', '--print', '%(title)s|%(thumbnail)s', url],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        line = result.stdout.strip()
        print(f"DEBUG: yt-dlp metadata output={line}")
        if "|" in line:
            title, thumbnail = line.split("|", 1)
        else:
            title, thumbnail = line, ""
        print(f"DEBUG: title={title}, thumbnail={thumbnail}")
        return title, thumbnail
    except Exception as e:
        print(f"ERROR: yt-dlp metadata extraction failed: {e}")
        return "", ""

def has_real_media(tweet):
    has = hasattr(tweet, "_media") and isinstance(tweet._media, list) and len(tweet._media) > 0
    print(f"DEBUG: has_real_media: hasattr(tweet, '_media')={hasattr(tweet, '_media')}, type={type(getattr(tweet, '_media', None))}, value={getattr(tweet, '_media', None)} => has={has}")
    return has

async def save_and_get_media_urls(tweet):
    print("DEBUG: save_and_get_media_urls called")
    ensure_media_dir()
    media_files = []
    tasks = []
    media_ok = has_real_media(tweet)
    if not media_ok:
        print("DEBUG: No media detected. Returning [].")
        return []
    async def save_photo(media, tweet_id, idx):
        filename = f"{tweet_id}_photo_{idx}.jpg"
        filepath = os.path.join(MEDIA_DIR, filename)
        if not os.path.exists(filepath):
            await media.download(filepath)
            print(f"✅ Saved photo: {filepath}")
        else:
            print(f"Photo already exists: {filepath}")
        return filename
    async def save_video(media, tweet_id, idx):
        filename = f"{tweet_id}_video_{idx}.mp4"
        filepath = os.path.join(MEDIA_DIR, filename)
        if not os.path.exists(filepath):
            await media.streams[-1].download(filepath)
            print(f"✅ Saved video: {filepath}")
        else:
            print(f"Video already exists: {filepath}")
        return filename
    async def save_gif(media, tweet_id, idx):
        filename = f"{tweet_id}_animated_gif_{idx}.mp4"
        filepath = os.path.join(MEDIA_DIR, filename)
        if not os.path.exists(filepath):
            await media.streams[-1].download(filepath)
            print(f"✅ Saved animated gif: {filepath}")
        else:
            print(f"Animated gif already exists: {filepath}")
        return filename
    for idx, media in enumerate(tweet.media):
        print(f"DEBUG: media idx={idx}, type={getattr(media, 'type', None)}")
        if hasattr(media, "type"):
            if media.type == "photo":
                tasks.append(save_photo(media, tweet.id, idx))
            if media.type == "animated_gif":
                tasks.append(save_gif(media, tweet.id, idx))
            if media.type == "video":
                tasks.append(save_video(media, tweet.id, idx))
    results = await asyncio.gather(*tasks) if tasks else []
    media_files.extend(results)
    print(f"DEBUG: Final media_files = {media_files}")
    return media_files

def extract_tweet_info(tweet, max_depth=10, depth=0):
    user_obj = getattr(tweet, "user", None)
    user = getattr(user_obj, "screen_name", "") if user_obj else ""
    profile_image = getattr(user_obj, "profile_image_url", "") if user_obj else ""
    media_api_urls = []
    if has_real_media(tweet):
        for idx, media in enumerate(tweet.media):
            if hasattr(media, "type"):
                if media.type == "photo":
                    filename = f"{tweet.id}_photo_{idx}.jpg"
                    media_api_urls.append(f"/media/{filename}")
                elif media.type in ["video", "animated_gif"]:
                    filename = f"{tweet.id}_{media.type}_{idx}.mp4"
                    media_api_urls.append(f"/media/{filename}")
    info = {
        "id": getattr(tweet, "id", ""),
        "full_text": getattr(tweet, "full_text", getattr(tweet, "text", "")) or "",
        "user": user,
        "created_at": str(getattr(tweet, "created_at", "")) or "",
        "media": media_api_urls,
        "profile_image": profile_image,
        "like_count": getattr(tweet, "favorite_count", 0) or 0,
        "retweet_count": getattr(tweet, "retweet_count", 0) or 0,
        "bookmark_count": getattr(tweet, "bookmark_count", 0) or 0,
        "view_count": getattr(tweet, "view_count", 0) or 0,
    }
    quote_tweet = getattr(tweet, "quote", None)
    if quote_tweet and isinstance(quote_tweet, type(tweet)) and depth < max_depth:
        print(f"DEBUG: Extracting quote tweet at depth={depth}, quote id={getattr(quote_tweet, 'id', None)}")
        info["quote"] = extract_tweet_info(quote_tweet, max_depth=max_depth, depth=depth+1)
    else:
        info["quote"] = None
    return info

async def get_tweet_content(tweet_url):
    print(f"DEBUG: get_tweet_content called with URL={tweet_url}")
    tweet_url = sanitize_url(tweet_url)
    client = GuestClient()
    await client.activate()
    tweet_id = tweet_url.split("/status/")[-1].split("?")[0].strip()
    print(f"DEBUG: Extracted tweet_id = {tweet_id}")
    tweet = await client.get_tweet_by_id(tweet_id)
    print(f"DEBUG: tweet object = {tweet}")
    if has_real_media(tweet):
        print(f"DEBUG: Calling save_and_get_media_urls on main tweet id={tweet_id}")
        await save_and_get_media_urls(tweet)
    else:
        print("DEBUG: No media to download for main tweet.")

    def get_all_quote_tweets(tw, depth=0, max_depth=10):
        result = []
        if depth > max_depth:
            return result
        quote = getattr(tw, "quote", None)
        if quote and isinstance(quote, type(tw)):
            result.append(quote)
            result += get_all_quote_tweets(quote, depth+1, max_depth)
        return result

    for quoted in get_all_quote_tweets(tweet):
        if has_real_media(quoted):
            print(f"DEBUG: Calling save_and_get_media_urls on quoted tweet id={getattr(quoted, 'id', None)}")
            await save_and_get_media_urls(quoted)

    info = extract_tweet_info(tweet, max_depth=10)
    print(f"DEBUG: Final top-level tweet info dict keys: {list(info.keys())}")
    return info

@app.get("/")
def serve_html():
    print("DEBUG: Serving showpage.html")
    return FileResponse("showpage.html", media_type="text/html")

@app.get('/yt-muxed/{filename}')
async def yt_muxed(filename: str):
    fpath = os.path.join(TMP_DIR, filename)
    print(f"DEBUG: yt-muxed requested for {fpath}")
    if not os.path.exists(fpath):
        print(f"DEBUG: yt-muxed file not found: {fpath}")
        return JSONResponse({"error": "Not found"}, status_code=404)
    print(f"DEBUG: yt-muxed file served: {fpath}")
    return FileResponse(fpath, media_type='video/mp4')

@app.get("/api/tweet")
async def api_tweet(url: str = Query(...)):
    print(f"DEBUG: /api/tweet called, param url type={type(url)}, value={url}")
    tweet_url = sanitize_url(url)

    if is_youtube_url(tweet_url):
        print("DEBUG: Detected YouTube URL.")
        try:
            title, thumbnail = get_video_metadata(tweet_url)
            muxed_url, temp_muxed = get_youtube_muxed_stream(tweet_url)
            if temp_muxed:
                stream_url = f"/yt-muxed/{temp_muxed}"
            else:
                stream_url = muxed_url
            info = {
                "type": "youtube",
                "youtube_url": tweet_url,
                "stream_url": stream_url,
                "title": title,
                "thumbnail": thumbnail,
            }
            print(f"DEBUG: Returning YouTube info: {info}")
            return JSONResponse(info)
        except Exception as e:
            print(f"ERROR in YouTube handler: {e}")
            import traceback
            print(f"ERROR traceback: {traceback.format_exc()}")
            return JSONResponse({"error": str(e)}, status_code=500)

    if is_rumble_url(tweet_url):
        print("DEBUG: Detected Rumble URL.")
        try:
            stream_url = get_rumble_stream_url(tweet_url)
            title, thumbnail = get_video_metadata(tweet_url)
            info = {
                "type": "rumble",
                "rumble_url": tweet_url,
                "stream_url": stream_url,
                "title": title,
                "thumbnail": thumbnail,
            }
            print(f"DEBUG: Returning Rumble info: {info}")
            return JSONResponse(info)
        except Exception as e:
            print(f"ERROR in Rumble handler: {e}")
            import traceback
            print(f"ERROR traceback: {traceback.format_exc()}")
            return JSONResponse({"error": str(e)}, status_code=500)

    # X/Twitter fallback
    try:
        print("DEBUG: Handling as X/Twitter post.")
        result = await get_tweet_content(tweet_url)
        result['type'] = "x"
        print(f"DEBUG: API successful. Result keys: {list(result.keys())}")
        return JSONResponse(result)
    except Exception as e:
        print(f"ERROR in api_tweet: {e}")
        import traceback
        print(f"ERROR traceback: {traceback.format_exc()}")
        return JSONResponse({"error": str(e)}, status_code=500)

if __name__ == "__main__":
    test_url = "https://x.com/BasedBeffJezos/status/1967771947703660580"
    print(f"DEBUG: __main__ mode. Fetching test tweet: {test_url}")
    loop = asyncio.get_event_loop()
    tweet_data = loop.run_until_complete(get_tweet_content(test_url))
    print("DEBUG: TEST RESULT:")
    for k, v in tweet_data.items():
        print(f"{k}: {v}")
