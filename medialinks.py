import mwclient
import mwparserfromhell
import logging
import re
import sys

def run(mother, categories):
    for category in categories:
        for page in mother.categories[category]:
            text = page.text()
            p =  mwparserfromhell.parse(text)
            has_bad_link = False
            for link in p.filter_wikilinks():
                if "File:" in link.title:
                    print("Fixing link", link.title, "in", page.name)
                    has_bad_link = True
                    link.title = re.sub("^:?File:", "Media:", str(link.title))

            if has_bad_link:
                page.save(str(p), "Automated edit to make File: links into direct Media: links")
