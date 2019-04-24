import mwclient
import mwparserfromhell
import logging
import re
import sys

def fix(page):
    text = page.text()
    p = mwparserfromhell.parse(text)
    global has_bad_link
    has_bad_link = False
    if "#REDIRECT" in p:
        print(page.name, "links to empty redirect page, fixing link...\n" )
        red = p.filter_wikilinks()
        has_bad_link = True
        for link in red:
            red_link = link.title
            return red_link
              
def run_pages(mother, pages):
    for title in pages:
        page = mother.pages[title]
        text = page.text()
        p =  mwparserfromhell.parse(text)
        print(p)
        for link in p.filter_wikilinks():
            link_title = str(link.title)
            link_page = mother.pages[link_title]
            red_link = fix(link_page)
            if has_bad_link:
                p.replace(link.title,red_link)
                print(p)
                page.save(str(p), "Automated edit to make links to redirected pages link to proper page instead")
