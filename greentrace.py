
import csv
import json
import re
import time
import html
from datetime import datetime, timezone
from urllib.parse import quote_plus, urlparse, parse_qs
from urllib.request import Request, urlopen
from html.parser import HTMLParser

APP_NAME = "GreenTrace OSINT"

SEARCHES = {
    "Company and Ownership": [
        '"{brand}" parent company ownership',
        '"{brand}" official company information',
        '"{brand}" legal company name'
    ],
    "Manufacturing and Suppliers": [
        '"{brand}" supplier list factories',
        '"{brand}" manufacturing locations',
        '"{brand}" supply chain sustainability report'
    ],
    "Environment and Labor": [
        '"{brand}" environmental violations',
        '"{brand}" labor compliance records',
        '"{brand}" environmental reports'
    ],
    "Certifications": [
        '"{brand}" certifications',
        '"{brand}" sustainability certification'
    ]
}


def clean_text(text):
    text = html.unescape(text or "")
    return re.sub(r"\s+", " ", text).strip()


class SearchParser(HTMLParser):

    def __init__(self):
        super().__init__()
        self.results = []
        self.current_url = None
        self.current_title = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)

        if tag == "a" and "result__a" in attrs.get("class", ""):
            self.current_url = attrs.get("href")
            self.current_title = []

    def handle_data(self, data):
        if self.current_url:
            self.current_title.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.current_url:
            title = clean_text(" ".join(self.current_title))
            url = html.unescape(self.current_url)

            if title and url.startswith("http"):
                parsed = urlparse(url)

                if "duckduckgo.com" in parsed.netloc:
                    target = parse_qs(parsed.query).get("uddg", [""])[0]
                    if target:
                        url = target

                if url.startswith("http"):
                    self.results.append({
                        "title": title,
                        "url": url
                    })

            self.current_url = None
            self.current_title = []


def search_web(query, limit=5):

    search_url = (
        "https://html.duckduckgo.com/html/?q="
        + quote_plus(query)
    )

    request = Request(
        search_url,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    with urlopen(request, timeout=15) as response:
        page = response.read().decode(
            "utf-8", errors="replace"
        )

    parser = SearchParser()
    parser.feed(page)

    results = []
    seen = set()

    for result in parser.results:
        if result["url"] not in seen:
            seen.add(result["url"])
            results.append(result)

        if len(results) >= limit:
            break

    return results


def investigate(brand):

    evidence = []
    seen = set()

    print("\nStarting GreenTrace investigation...")
    print("--------------------------------------")

    for category, queries in SEARCHES.items():

        print("\nCategory:", category)

        for template in queries:

            query = template.format(brand=brand)

            print("Searching:", query)

            try:
                results = search_web(query)

                for result in results:

                    if result["url"] in seen:
                        continue

                    seen.add(result["url"])

                    evidence.append({
                        "category": category,
                        "title": result["title"],
                        "url": result["url"],
                        "search_query": query,
                        "retrieved_at": datetime.now(
                            timezone.utc
                        ).isoformat(timespec="seconds")
                    })

            except Exception as error:
                print("Search error:", error)

            time.sleep(1)

    return evidence


def save_json(brand, evidence):

    filename = "GreenTrace_Report.json"

    data = {
        "tool": APP_NAME,
        "brand": brand,
        "generated_at": datetime.now().isoformat(),
        "evidence": evidence
    }

    with open(filename, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)

    print("JSON report saved:", filename)


def save_csv(evidence):

    filename = "GreenTrace_Report.csv"

    fields = [
        "category",
        "title",
        "url",
        "search_query",
        "retrieved_at"
    ]

    with open(
        filename,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fields
        )

        writer.writeheader()
        writer.writerows(evidence)

    print("CSV report saved:", filename)


def save_txt(brand, evidence):

    filename = "GreenTrace_Report.txt"

    with open(filename, "w", encoding="utf-8") as file:

        file.write("GREENTRACE OSINT REPORT\n")
        file.write("======================\n\n")

        file.write("Company: " + brand + "\n")
        file.write(
            "Date: " + datetime.now().strftime(
                "%Y-%m-%d %H:%M"
            ) + "\n\n"
        )

        file.write(
            "IMPORTANT: These are public search results "
            "and must be verified using original sources.\n\n"
        )

        for item in evidence:

            file.write("\nCategory: " + item["category"])
            file.write("\nTitle: " + item["title"])
            file.write("\nSource: " + item["url"])
            file.write("\nRetrieved: " + item["retrieved_at"])
            file.write("\n" + "-" * 50 + "\n")

    print("Text report saved:", filename)


def main():

    print("=" * 50)
    print("       GREENTRACE OSINT")
    print(" Corporate Supply Chain Analyzer")
    print("=" * 50)

    brand = input("\nEnter company or brand name: ").strip()

    if not brand:
        print("Please enter a company name.")
        return

    evidence = investigate(brand)

    print("\nInvestigation completed.")
    print("Total sources found:", len(evidence))

    if not evidence:
        print("No results found.")
        return

    save_json(brand, evidence)
    save_csv(evidence)
    save_txt(brand, evidence)

    print("\nAll reports have been created.")
    print("Check your project folder.")


if __name__ == "__main__":
    main()
