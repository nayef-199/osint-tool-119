
import csv
import json
import re
import html
import time
import threading
import queue
import webbrowser

from datetime import datetime, timezone
from urllib.parse import quote_plus, urlparse, parse_qs, unquote
from urllib.request import Request, urlopen
from html.parser import HTMLParser

import tkinter as tk
from tkinter import ttk, messagebox, filedialog


APP_NAME = "GreenTrace OSINT"

SEARCHES = {
    "Company and Ownership": [
        "{brand} parent company ownership",
        "{brand} official company profile",
        "{brand} legal company name"
    ],

    "Manufacturing and Suppliers": [
        "{brand} supplier list factories",
        "{brand} manufacturing locations",
        "{brand} supply chain report"
    ],

    "Environment and Labor": [
        "{brand} environmental violations",
        "{brand} labor compliance records",
        "{brand} environmental reports"
    ],

    "Certifications": [
        "{brand} sustainability certifications",
        "{brand} ethical manufacturing certification",
        "{brand} environmental certification"
    ]
}


# ----------------------------------------
# HTML CLEANING
# ----------------------------------------

def clean_text(text):
    text = html.unescape(text or "")
    return re.sub(r"\s+", " ", text).strip()


# ----------------------------------------
# SEARCH RESULT PARSER
# ----------------------------------------

class SearchParser(HTMLParser):

    def __init__(self):
        super().__init__()

        self.results = []
        self.current_url = None
        self.current_title = []
        self.current_is_result = False

    def handle_starttag(self, tag, attrs):

        attrs = dict(attrs)

        if tag == "a":

            href = attrs.get("href", "")
            classes = attrs.get("class", "").split()

            is_result = (
                "result__a" in classes
                or "result-link" in classes
            )

            if href and is_result:
                self.current_url = href
                self.current_title = []
                self.current_is_result = True

    def handle_data(self, data):

        if self.current_is_result:
            self.current_title.append(data)

    def handle_endtag(self, tag):

        if tag == "a" and self.current_is_result:

            title = clean_text(" ".join(self.current_title))
            url = html.unescape(self.current_url)

            if url.startswith("//"):
                url = "https:" + url

            parsed = urlparse(url)

            # Handle DuckDuckGo redirect links
            if "duckduckgo.com" in parsed.netloc:
                target = parse_qs(parsed.query).get(
                    "uddg", [""]
                )[0]

                if target:
                    url = unquote(target)

            if title and url.startswith("http"):

                domain = urlparse(url).netloc.lower()

                if "duckduckgo.com" not in domain:
                    self.results.append({
                        "title": title,
                        "url": url
                    })

            self.current_url = None
            self.current_title = []
            self.current_is_result = False


# ----------------------------------------
# REAL WEB SEARCH
# ----------------------------------------

def search_web(query, limit=5):

    search_url = (
        "https://html.duckduckgo.com/html/?q="
        + quote_plus(query)
    )

    request = Request(
        search_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9"
        }
    )

    with urlopen(request, timeout=20) as response:

        page = response.read().decode(
            "utf-8", errors="replace"
        )

    if (
        "anomaly-modal" in page.lower()
        or "bots use duckduckgo" in page.lower()
    ):
        raise Exception(
            "DuckDuckGo temporarily blocked automated searching."
        )

    parser = SearchParser()
    parser.feed(page)

    results = []
    seen = set()

    for result in parser.results:

        url = result["url"]

        if url not in seen:
            seen.add(url)
            results.append(result)

        if len(results) >= limit:
            break

    return results


# ----------------------------------------
# MAIN INVESTIGATION
# ----------------------------------------

def investigate(brand, message_callback, result_callback):

    evidence = []
    seen = set()

    queries = []

    for category, templates in SEARCHES.items():

        for template in templates:

            queries.append((
                category,
                template.format(brand=brand)
            ))

    total = len(queries)

    for index, (category, query) in enumerate(queries, 1):

        message_callback(
            f"[{index}/{total}] Searching: {query}"
        )

        try:

            results = search_web(query, limit=5)

            message_callback(
                f"Found {len(results)} results."
            )

            for result in results:

                if result["url"] in seen:
                    continue

                seen.add(result["url"])

                item = {
                    "category": category,
                    "title": result["title"],
                    "url": result["url"],
                    "search_query": query,
                    "retrieved_at": datetime.now(
                        timezone.utc
                    ).isoformat(timespec="seconds")
                }

                evidence.append(item)

                result_callback(item)

        except Exception as error:

            message_callback(
                f"Search error: {error}"
            )

        time.sleep(1)

    return evidence


# ----------------------------------------
# SAVE REPORTS
# ----------------------------------------

def export_report(brand, evidence, file_type):

    timestamp = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    if file_type == "json":

        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialfile="GreenTrace_Report.json"
        )

        if not filename:
            return

        data = {
            "tool": APP_NAME,
            "brand": brand,
            "generated_at": timestamp,
            "total_sources": len(evidence),
            "evidence": evidence
        }

        with open(filename, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)

    elif file_type == "csv":

        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile="GreenTrace_Report.csv"
        )

        if not filename:
            return

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
            encoding="utf-8-sig"
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=fields
            )

            writer.writeheader()
            writer.writerows(evidence)

    elif file_type == "txt":

        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")],
            initialfile="GreenTrace_Report.txt"
        )

        if not filename:
            return

        with open(filename, "w", encoding="utf-8") as file:

            file.write("GREENTRACE OSINT REPORT\n")
            file.write("=" * 55 + "\n\n")

            file.write("Company: " + brand + "\n")
            file.write("Date: " + timestamp + "\n")
            file.write(
                "Total sources: " + str(len(evidence)) + "\n\n"
            )

            file.write(
                "NOTE: Search results are leads, not verified "
                "evidence of compliance or violations.\n"
            )

            for item in evidence:

                file.write("\n" + "-" * 55 + "\n")
                file.write(
                    "Category: " + item["category"] + "\n"
                )
                file.write(
                    "Title: " + item["title"] + "\n"
                )
                file.write(
                    "URL: " + item["url"] + "\n"
                )
                file.write(
                    "Retrieved: " + item["retrieved_at"] + "\n"
                )

    messagebox.showinfo(
        "Export complete",
        "Your report has been saved successfully."
    )


# ----------------------------------------
# DASHBOARD
# ----------------------------------------

class GreenTraceDashboard:

    def __init__(self, root):

        self.root = root
        self.root.title("GreenTrace OSINT | Dashboard")
        self.root.geometry("1150x750")
        self.root.minsize(900, 600)

        self.results = []
        self.events = queue.Queue()
        self.searching = False
        self.brand = ""

        self.setup_style()
        self.create_dashboard()

        self.root.after(100, self.process_events)

    # ------------------------------------

    def setup_style(self):

        self.root.configure(bg="#101820")

        style = ttk.Style()

        style.theme_use("clam")

        style.configure(
            "Treeview",
            background="#202d38",
            foreground="white",
            fieldbackground="#202d38",
            rowheight=30,
            borderwidth=0
        )

        style.configure(
            "Treeview.Heading",
            background="#263b49",
            foreground="white",
            font=("Arial", 10, "bold")
        )

        style.map(
            "Treeview",
            background=[("selected", "#087f8c")],
            foreground=[("selected", "white")]
        )

    # ------------------------------------

    def create_dashboard(self):

        # HEADER

        header = tk.Frame(
            self.root,
            bg="#087f8c",
            height=90
        )

        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(
            header,
            text="GREENTRACE OSINT",
            font=("Arial", 24, "bold"),
            fg="white",
            bg="#087f8c"
        ).pack(anchor="w", padx=25, pady=(15, 0))

        tk.Label(
            header,
            text="Corporate Supply Chain & Environmental Footprint Analyzer",
            font=("Arial", 10),
            fg="#d8f5f5",
            bg="#087f8c"
        ).pack(anchor="w", padx=27)

        # MAIN CONTAINER

        main = tk.Frame(
            self.root,
            bg="#101820"
        )

        main.pack(
            fill="both",
            expand=True,
            padx=20,
            pady=15
        )

        # SEARCH AREA

        search_frame = tk.Frame(
            main,
            bg="#1b2a35",
            padx=15,
            pady=15
        )

        search_frame.pack(fill="x", pady=(0, 12))

        tk.Label(
            search_frame,
            text="Company / Brand Name",
            font=("Arial", 11, "bold"),
            fg="white",
            bg="#1b2a35"
        ).pack(anchor="w")

        input_row = tk.Frame(
            search_frame,
            bg="#1b2a35"
        )

        input_row.pack(fill="x", pady=8)

        self.brand_entry = tk.Entry(
            input_row,
            font=("Arial", 13),
            bg="#263b49",
            fg="white",
            insertbackground="white",
            relief="flat"
        )

        self.brand_entry.pack(
            side="left",
            fill="x",
            expand=True,
            ipady=9,
            padx=(0, 10)
        )

        self.brand_entry.bind(
            "<Return>",
            lambda event: self.start_search()
        )

        self.search_button = tk.Button(
            input_row,
            text="START INVESTIGATION",
            command=self.start_search,
            bg="#087f8c",
            fg="white",
            font=("Arial", 10, "bold"),
            relief="flat",
            padx=15,
            pady=10,
            cursor="hand2"
        )

        self.search_button.pack(side="right")

        # STATISTICS

        stats = tk.Frame(
            main,
            bg="#101820"
        )

        stats.pack(fill="x", pady=(0, 12))

        self.total_label = self.create_stat(
            stats, "TOTAL SOURCES", "0"
        )

        self.company_label = self.create_stat(
            stats, "OWNERSHIP", "0"
        )

        self.supplier_label = self.create_stat(
            stats, "SUPPLIERS", "0"
        )

        self.environment_label = self.create_stat(
            stats, "ENVIRONMENT / LABOR", "0"
        )

        self.certification_label = self.create_stat(
            stats, "CERTIFICATIONS", "0"
        )

        # RESULTS

        results_frame = tk.Frame(
            main,
            bg="#1b2a35",
            padx=12,
            pady=12
        )

        results_frame.pack(
            fill="both",
            expand=True
        )

        tk.Label(
            results_frame,
            text="INVESTIGATION RESULTS",
            font=("Arial", 13, "bold"),
            fg="white",
            bg="#1b2a35"
        ).pack(anchor="w", pady=(0, 10))

        columns = (
            "category",
            "title",
            "url"
        )

        self.tree = ttk.Treeview(
            results_frame,
            columns=columns,
            show="headings"
        )

        self.tree.heading(
            "category",
            text="CATEGORY"
        )

        self.tree.heading(
            "title",
            text="SEARCH RESULT"
        )

        self.tree.heading(
            "url",
            text="SOURCE WEBSITE"
        )

        self.tree.column(
            "category",
            width=170
        )

        self.tree.column(
            "title",
            width=400
        )

        self.tree.column(
            "url",
            width=400
        )

        scrollbar = ttk.Scrollbar(
            results_frame,
            orient="vertical",
            command=self.tree.yview
        )

        self.tree.configure(
            yscrollcommand=scrollbar.set
        )

        self.tree.pack(
            side="left",
            fill="both",
            expand=True
        )

        scrollbar.pack(
            side="right",
            fill="y"
        )

        self.tree.bind(
            "<Double-1>",
            self.open_result
        )

        # LOGS

        log_frame = tk.Frame(
            main,
            bg="#1b2a35",
            padx=12,
            pady=10
        )

        log_frame.pack(fill="x", pady=12)

        tk.Label(
            log_frame,
            text="INVESTIGATION ACTIVITY",
            font=("Arial", 10, "bold"),
            fg="white",
            bg="#1b2a35"
        ).pack(anchor="w")

        self.log_box = tk.Text(
            log_frame,
            height=5,
            bg="#101820",
            fg="#8ee6c1",
            font=("Consolas", 9),
            relief="flat",
            state="disabled"
        )

        self.log_box.pack(fill="x", pady=7)

        # EXPORT BUTTONS

        buttons = tk.Frame(
            main,
            bg="#101820"
        )

        buttons.pack(fill="x")

        self.export_button(
            buttons, "EXPORT JSON", "json"
        )

        self.export_button(
            buttons, "EXPORT CSV", "csv"
        )

        self.export_button(
            buttons, "EXPORT TXT", "txt"
        )

        self.status = tk.Label(
            buttons,
            text="Ready",
            bg="#101820",
            fg="#8ee6c1",
            font=("Arial", 10)
        )

        self.status.pack(side="right", padx=10)

    # ------------------------------------

    def create_stat(self, parent, title, value):

        frame = tk.Frame(
            parent,
            bg="#1b2a35",
            padx=12,
            pady=12
        )

        frame.pack(
            side="left",
            fill="both",
            expand=True,
            padx=4
        )

        tk.Label(
            frame,
            text=title,
            font=("Arial", 8, "bold"),
            fg="#9eb5c5",
            bg="#1b2a35"
        ).pack(anchor="w")

        label = tk.Label(
            frame,
            text=value,
            font=("Arial", 22, "bold"),
            fg="#38c9b2",
            bg="#1b2a35"
        )

        label.pack(anchor="w")

        return label

    # ------------------------------------

    def export_button(self, parent, text, file_type):

        button = tk.Button(
            parent,
            text=text,
            command=lambda: self.export(file_type),
            bg="#263b49",
            fg="white",
            font=("Arial", 9, "bold"),
            relief="flat",
            padx=15,
            pady=9,
            cursor="hand2"
        )

        button.pack(side="left", padx=4)

    # ------------------------------------

    def log(self, message):

        self.log_box.configure(state="normal")

        timestamp = datetime.now().strftime("%H:%M:%S")

        self.log_box.insert(
            "end",
            f"[{timestamp}] {message}\n"
        )

        self.log_box.see("end")

        self.log_box.configure(state="disabled")

    # ------------------------------------

    def start_search(self):

        if self.searching:
            return

        brand = self.brand_entry.get().strip()

        if not brand:
            messagebox.showwarning(
                "Missing company",
                "Please enter a company or brand name."
            )
            return

        self.brand = brand
        self.results = []

        for item in self.tree.get_children():
            self.tree.delete(item)

        self.update_statistics()

        self.searching = True

        self.search_button.configure(
            state="disabled",
            text="SEARCHING..."
        )

        self.status.configure(
            text="Investigation running..."
        )

        self.log(f"Starting investigation for {brand}")

        thread = threading.Thread(
            target=self.worker,
            args=(brand,),
            daemon=True
        )

        thread.start()

    # ------------------------------------

    def worker(self, brand):

        def send_log(message):
            self.events.put(("log", message))

        def send_result(item):
            self.events.put(("result", item))

        try:

            evidence = investigate(
                brand,
                send_log,
                send_result
            )

            self.events.put(
                ("done", evidence)
            )

        except Exception as error:

            self.events.put(
                ("fatal", str(error))
            )

    # ------------------------------------

    def process_events(self):

        try:

            while True:

                event, data = self.events.get_nowait()

                if event == "log":

                    self.log(data)

                elif event == "result":

                    self.results.append(data)

                    self.tree.insert(
                        "",
                        "end",
                        values=(
                            data["category"],
                            data["title"],
                            data["url"]
                        )
                    )

                    self.update_statistics()

                elif event == "done":

                    self.results = data

                    self.searching = False

                    self.search_button.configure(
                        state="normal",
                        text="START INVESTIGATION"
                    )

                    self.status.configure(
                        text="Investigation completed"
                    )

                    self.log(
                        f"Investigation completed. "
                        f"{len(data)} sources collected."
                    )

                    if not data:
                        self.log(
                            "No results returned. Check internet "
                            "connection or search engine access."
                        )

                elif event == "fatal":

                    self.searching = False

                    self.search_button.configure(
                        state="normal",
                        text="START INVESTIGATION"
                    )

                    self.status.configure(
                        text="Investigation failed"
                    )

                    self.log("ERROR: " + data)

                    messagebox.showerror(
                        "Investigation error",
                        data
                    )

        except queue.Empty:
            pass

        self.root.after(
            100,
            self.process_events
        )

    # ------------------------------------

    def update_statistics(self):

        categories = {
            "Company and Ownership": 0,
            "Manufacturing and Suppliers": 0,
            "Environment and Labor": 0,
            "Certifications": 0
        }

        for item in self.results:

            category = item["category"]

            if category in categories:
                categories[category] += 1

        self.total_label.configure(
            text=str(len(self.results))
        )

        self.company_label.configure(
            text=str(categories["Company and Ownership"])
        )

        self.supplier_label.configure(
            text=str(categories["Manufacturing and Suppliers"])
        )

        self.environment_label.configure(
            text=str(categories["Environment and Labor"])
        )

        self.certification_label.configure(
            text=str(categories["Certifications"])
        )

    # ------------------------------------

    def open_result(self, event):

        selected = self.tree.selection()

        if not selected:
            return

        values = self.tree.item(
            selected[0],
            "values"
        )

        if len(values) >= 3:

            webbrowser.open(values[2])

    # ------------------------------------

    def export(self, file_type):

        if not self.results:

            messagebox.showwarning(
                "No results",
                "Complete an investigation before exporting."
            )

            return

        export_report(
            self.brand,
            self.results,
            file_type
        )


# ----------------------------------------
# START APPLICATION
# ----------------------------------------

if __name__ == "__main__":

    root = tk.Tk()

    app = GreenTraceDashboard(root)

    root.mainloop()

