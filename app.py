from flask import Flask, render_template, request, flash
import feedparser
from nltk.sentiment import SentimentIntensityAnalyzer
import nltk
import logging
from urllib.parse import urlparse
import html
import os

#custom NLTK data path
nltk.data.path.append(os.path.join(os.path.dirname(__file__), "nltk_data"))

# Now download will work without errors
nltk.download('vader_lexicon', download_dir=nltk.data.path[0])

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
logging.basicConfig(level=logging.DEBUG)

# Updated RSS Feed URLs including The Hindu sources
RSS_FEEDS = {
    "india": "https://feeds.feedburner.com/ndtvnews-india-news",
    "world": "https://feeds.feedburner.com/ndtvnews-world-news",
    "education": {
        "The Hindu Education": "https://www.thehindu.com/education/feeder/default.rss",
    },
    "agriculture": {
        "The Hindu Agriculture": "https://www.thehindu.com/sci-tech/agriculture/feeder/default.rss"
    },
    "health": "https://www.thehindu.com/sci-tech/health/feeder/default.rss",
    "sports": "https://www.thehindu.com/sport/feeder/default.rss",
    "economy": "https://www.thehindu.com/business/Economy/feeder/default.rss"
}

sia = SentimentIntensityAnalyzer()

def clean_html_content(text):
    """Remove HTML tags and decode HTML entities."""
    text = html.unescape(text)  # Decode HTML entities
    for tag in ['<p>', '</p>', '<br>', '<br/>', '<br />', '<div>', '</div>']:
        text = text.replace(tag, ' ')
    return text.strip()

def analyze_sentiment(text):
    """Perform sentiment analysis and return the sentiment label."""
    score = sia.polarity_scores(text)['compound']
    if score >= 0.05:
        return "Positive 😊"
    elif score <= -0.05:
        return "Negative 😞"
    else:
        return "Neutral 😐"

def validate_feed_url(url):
    """Validate the feed URL structure."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False

def fetch_feed(url, source_name=""):
    """Fetch and parse the RSS feed with error handling."""
    if not validate_feed_url(url):
        logging.error(f"Invalid URL format for {source_name}: {url}")
        return None
    
    try:
        feed = feedparser.parse(url)
        if feed.bozo:
            logging.error(f"Feed parsing error for {source_name}: {feed.bozo_exception}")
            return None
        return feed
    except Exception as e:
        logging.error(f"Error fetching feed from {source_name}: {str(e)}")
        return None

def process_feed_entry(entry, source_name=""):
    """Process a single feed entry and return article data."""
    try:
        image_url = None
        if hasattr(entry, 'media_content') and entry.media_content:
            image_url = entry.media_content[0].get("url")
        elif hasattr(entry, 'links'):
            for link in entry.links:
                if link.get('type', '').startswith('image'):
                    image_url = link.get('href')
                    break

        summary = entry.get('summary', entry.get('description', ''))
        summary = clean_html_content(summary)
        published = entry.get('published', entry.get('updated', 'No date'))

        return {
            "source": source_name,
            "title": entry.get('title', 'No title'),
            "link": entry.get('link', '#'),
            "published": published,
            "summary": summary,
            "image": image_url,
            "sentiment": analyze_sentiment(summary)
        }
    except Exception as e:
        logging.error(f"Error processing entry from {source_name}: {str(e)}")
        return None

from dateutil import parser

@app.route('/', methods=["GET", "POST"])
def home():
    category = request.form.get('category', 'india')
    articles = []
    
    if category in ['education', 'agriculture']:
        for source_name, url in RSS_FEEDS[category].items():
            feed = fetch_feed(url, source_name)
            if feed:
                for entry in feed.entries:
                    article = process_feed_entry(entry, source_name)
                    if article:
                        articles.append(article)
    else:
        feed = fetch_feed(RSS_FEEDS.get(category, ""))
        if feed:
            for entry in feed.entries:
                article = process_feed_entry(entry, category)
                if article:
                    articles.append(article)
    
    if not articles:
        flash(f"No articles found for {category} category.", "warning")

    # **Sort articles by most recent first**
    def get_published_date(article):
        try:
            return parser.parse(article['published'])
        except (ValueError, TypeError):
            return None

    articles = sorted([a for a in articles if get_published_date(a) is not None], 
                      key=get_published_date, reverse=True)

    return render_template('index.html', articles=articles, category=category)


if __name__ == "__main__":
    app.run(debug=True)
