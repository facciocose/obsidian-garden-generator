from __future__ import annotations

import http.server
import re
import time
from collections import defaultdict
from concurrent.futures import thread
from configparser import ConfigParser
from os import path
from threading import Thread

import markdown
import sass
from jinja2 import Environment, FileSystemLoader
from slugify import slugify
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

LINK_REGEX = r"\[\[([^\]\[]+\|)?([^\]\[]+)\]\]"


def load_config():
    config = ConfigParser()
    try:
        config.read_file(open("config.ini"))
    except FileNotFoundError:
        print("Missing config.ini")
        exit(1)
    return config["DEFAULT"]


config = load_config()

env = Environment(loader=FileSystemLoader(config["TEMPLATES_DIR"]))


class Page:
    name: str
    is_index: bool
    markdown: str
    html: str
    links: set[Page]
    backlinks: set[Page]

    def __init__(self, name, is_index=False) -> None:
        self.name = name
        self.is_index = is_index
        self.markdown = ""
        self.html = ""
        self.links = set()
        self.backlinks = set()
        self.mtime = None

    def __repr__(self) -> str:
        return self.name

    def __str__(self) -> str:
        return self.name

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, __o: object) -> bool:
        return self.name == __o.name

    @property
    def markdown_name(self) -> str:
        return f"{self.name}.md"

    @property
    def markdown_path(self) -> str:
        return path.join(config["BASE_DIR"], self.markdown_name)

    @property
    def html_name(self) -> str:
        filename = "index" if self.is_index else slugify(self.name)
        return f"{filename}.html"

    def parse(self):
        with open(self.markdown_path, "r") as f:
            self.markdown = f.read()
        self.links = {
            Page(link[0][:-1]) if link[0] else Page(link[1])
            for link in re.findall(LINK_REGEX, self.markdown)
        }
        html = markdown.markdown(
            self.markdown, extensions=["codehilite", "fenced_code", "tables"]
        )
        self.html = re.sub(LINK_REGEX, self._create_link, html)
        self.mtime = time.strftime(
            "%Y.%m.%d", time.localtime(path.getmtime(self.markdown_path))
        )
        self.compute_backlinks()

    @staticmethod
    def _create_link(match) -> str:
        name = match.group(2)
        if link := match.group(1):
            filename = slugify(link[:-1]) + ".html"
        else:
            filename = slugify(name) + ".html"
        return f'<a href="{filename}">{name}</a>'

    def compute_backlinks(self):
        for link in self.links:
            backlinks[link].add(self)

    def save(self):
        template = env.get_template("index.html")
        content = template.render(
            content=self.html,
            mtime=self.mtime,
            name=self.name,
            is_index=self.is_index,
            backlinks=sorted(backlinks[self], key=lambda x: 0 if x.is_index else 1),
        )

        with open(path.join(config["OUTPUT_DIR"], self.html_name), "w") as f:
            f.write(content)


backlinks = defaultdict(set)
pages = set()


def create_page(name, is_index=False):
    page = Page(name, is_index)
    page.parse()
    pages.add(page)

    for link in page.links:
        create_page(link.name)

def process_site():
    sass.compile(
        dirname=(
            path.join(config["STATIC_DIR"], "sass"),
            path.join(config["OUTPUT_DIR"], "css"),
        ),
        output_style="compressed",
    )
    create_page(config["START_PAGE"], is_index=True)

    for page in pages:
        page.save()

class TemplateUpdateHandler(FileSystemEventHandler):
    VALID_PATHS = [
        path.abspath(config["TEMPLATES_DIR"]),
        path.abspath(path.join(config["STATIC_DIR"], "sass")),
    ]

    def on_any_event(self, event):
        if event.is_directory and path.abspath(event.src_path) in self.VALID_PATHS:
            process_site()


class HttpRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        kwargs["directory"] = config["OUTPUT_DIR"]
        super().__init__(*args, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()


def run():
    observer = Observer()
    observer.schedule(TemplateUpdateHandler(), ".", recursive=True)
    observer.start()
    process_site()

    httpd = http.server.HTTPServer(("", 8000), HttpRequestHandler)
    httpd_thread = Thread(target=httpd.serve_forever)
    httpd_thread.daemon = True
    httpd_thread.start()

    try:
        while observer.is_alive() or httpd_thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()
