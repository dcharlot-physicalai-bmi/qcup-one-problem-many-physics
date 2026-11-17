"""Plain text of a saved HTML page (script and style dropped; table cells separated by ' | ').
    python3 -I html2text.py IN.html OUT.txt"""
import sys
from html.parser import HTMLParser


class T(HTMLParser):
    def __init__(self):
        super().__init__(); self.out = []; self.skip = 0
    def handle_starttag(self, tag, a):
        if tag in ("script", "style"): self.skip += 1
        if tag in ("p", "div", "tr", "br", "li", "h1", "h2", "h3", "h4", "table", "section"): self.out.append("\n")
        if tag in ("td", "th"): self.out.append(" | ")
    def handle_endtag(self, tag):
        if tag in ("script", "style"): self.skip -= 1
    def handle_data(self, d):
        if not self.skip: self.out.append(d)


t = T(); t.feed(open(sys.argv[1], encoding="utf-8", errors="replace").read())
txt = "".join(t.out)
lines = [" ".join(l.split()) for l in txt.splitlines()]
open(sys.argv[2], "w").write("\n".join(l for l in lines if l) + "\n")
