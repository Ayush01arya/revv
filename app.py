import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import re

app = Flask(__name__)
CORS(app)

API_KEY = "435972e90f46963135e2ebabc9fc605b1e63e2308ba22325b203c740f812f982"


def normalize_domain(url):
    """Extracts and returns only the domain from any given URL format."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url  # Ensure proper URL format if not provided
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    if domain.startswith("www."):
        domain = domain[4:]  # Remove 'www.' if present
    return domain


def fetch_keywords(domain):
    params = {
        "api_key": API_KEY,
        "q": f"site:{domain}",
        "num": 100,
        "hl": "en",
        "gl": "us"
    }
    response = requests.get("https://serpapi.com/search", params=params)
    data = response.json()

    keywords = []
    if "organic_results" in data:
        for result in data["organic_results"]:
            if "title" in result:
                keywords.append(result["title"])
    return keywords


def classify_intents(keywords, domain):
    branded_count = 0
    intent_counts = {"Commercial": 0, "Transactional": 0, "Navigational": 0, "Informational": 0}

    for keyword in keywords:
        keyword_lower = keyword.lower()

        if domain in keyword_lower:
            branded_count += 1

        if re.search(r"(buy|order|discount|pricing|cheap|sale|cost)", keyword_lower):
            intent_counts["Transactional"] += 1
        elif re.search(r"(best|top|review|compare|vs|alternative|recommended)", keyword_lower):
            intent_counts["Commercial"] += 1
        elif re.search(r"(login|sign in|contact|support|official|website)", keyword_lower):
            intent_counts["Navigational"] += 1
        elif re.search(r"(how|guide|tips|tutorial|what|why|learn|strategy)", keyword_lower):
            intent_counts["Informational"] += 1

    total_keywords = len(keywords) if keywords else 1

    intent_percentages = {k: round((v / total_keywords) * 100, 2) for k, v in intent_counts.items()}
    branded_percentage = round((branded_count / total_keywords) * 100, 2)
    non_branded_percentage = 100 - branded_percentage

    return intent_percentages, branded_percentage, non_branded_percentage


@app.route('/analyze', methods=['POST'])
def analyze_website():
    try:
        data = request.json
        input_url = data.get('url', '').strip()
        if not input_url:
            return jsonify({"error": "URL is required."}), 400

        output_domain = normalize_domain(input_url)
        url = f"https://tools.trafficthinktank.com/website-traffic-checker?q={output_domain}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.google.com/"
        }

        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return jsonify({"error": f"Failed to retrieve page. Status Code: {response.status_code}"}), 400

        soup = BeautifulSoup(response.text, "html.parser")

        def extract_metric(metric_name):
            metric_section = soup.find("p", string=metric_name)
            if metric_section:
                value_tag = metric_section.find_next_sibling("p")
                if value_tag and value_tag.find("a"):
                    return value_tag.find("a").text.strip()
            return "Not Found"

        metrics = {
            "organic_traffic": extract_metric("Organic Search Traffic"),
            "traffic_value": extract_metric("Traffic Value"),
            "authority_score": extract_metric("Authority Score"),
            "visits": extract_metric("Visits"),
            "pages_per_visit": extract_metric("Pages / Visit"),
            "avg_visit_duration": extract_metric("Avg. Visit Duration"),
            "bounce_rate": extract_metric("Bounce Rate")
        }

        top_keywords = []
        keyword_table = soup.find("div", class_="table")
        if keyword_table:
            rows = keyword_table.find_all("tr")[1:]
            for row in rows:
                cols = row.find_all("td")
                if len(cols) >= 3:
                    top_keywords.append({
                        "keyword": cols[0].text.strip(),
                        "rank": cols[1].text.strip(),
                        "traffic_percentage": cols[2].text.strip()
                    })

        backlinks = []
        backlinks_section = soup.find("h3", string="Backlinks")
        if backlinks_section:
            backlinks_table = backlinks_section.find_next("table")
            if backlinks_table:
                rows = backlinks_table.find_all("tr")[1:]
                for row in rows:
                    cols = row.find_all("td")
                    if len(cols) >= 4:
                        backlinks.append({
                            "source_url": cols[0].find("a")["href"].strip(),
                            "target_url": cols[0].find_all("a")[-1]["href"].strip(),
                            "anchor_text": cols[1].text.strip(),
                            "follow_type": cols[2].text.strip()
                        })

        keywords = fetch_keywords(output_domain)
        intent_percentages, branded_percentage, non_branded_percentage = classify_intents(keywords, output_domain)

        return jsonify({
            "domain": output_domain,
            "metrics": metrics,
            "top_keywords": top_keywords,
            "backlinks": backlinks,
            "intent_percentages": intent_percentages,
            "branded_percentage": branded_percentage,
            "non_branded_percentage": non_branded_percentage
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
