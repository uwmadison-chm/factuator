import mwclient
import mwparserfromhell
import logging
import re
import sys

def fix(page):
    text = page.text()
    p = mwparserfromhell.parse(text)
    has_bad_link = False
    red_link = ""
    if "#REDIRECT" in p:
        logging.info(f"`{page.name}` is an empty redirect page, fixing link...")
        red = p.filter_wikilinks()
        has_bad_link = True
        for link in red:
            red_link = link.title
    return red_link, has_bad_link
              
def run_category(mother, category_name):
    category = mother.categories[category_name]
    for page in category:
        run_page(mother, page)


def run_pages(mother, pages):
    for title in pages:
        page = mother.pages[title]
        run_page(mother, page)

def run_page(mother, page):
    oldtext = page.text()
    p =  mwparserfromhell.parse(oldtext)
    link_titles = []
    
    # Replaces links to redirected pages with proper link
    for link in p.filter_wikilinks():
        link_title = str(link.title)
        link_page = mother.pages[link_title]
        red_link, has_bad_link = fix(link_page)
        if has_bad_link:
            link_titles.append(link_title)
            p.replace(link.title, red_link)
    newpage = str(p)
    
    if oldtext != newpage:
        logging.warning("Updating %s page, change detected\n", page.name)
        page.save(newpage, "Automated edit to make links to redirected pages link to proper page instead")
        
    # Optional: Look for same redirect pages on entire MOTHER wiki. Replaces appropriate links and deleting redirect pages when no longer being used
    if len(link_titles) > 0 :
        # TODO: disabling for now
        return
        replace_all = input("Search the rest of the Wiki for these redirected links? [y/n]:")
        while (len(replace_all) >= 1):
        
            if replace_all.upper() == 'Y':
                link_index = 0
                for link_index in range(len(link_titles)):
                    page_link = mother.pages[link_titles[link_index]]
                    links_here = page_link.backlinks(filterredir = 'all', redirect = True, limit = None)
                    new_index = 0
                    for page in links_here:
                        bad_page = mother.pages[page.name]
                        badtext = bad_page.text()
                        bp = mwparserfromhell.parse(badtext)
                        for link in bp.filter_wikilinks():
                            for new_index in range(len(link_titles)):
                                if link.title == (link_titles[new_index]):
                                    bp.replace(link.title, red_link)
                        newpage = str(bp) 
                    
                        if badtext != newpage:
                            logging.warning("Updating %s page, change detected\n", bad_page.name)
                            page.save(newpage, "Automated edit to make links to redirected pages link to proper page instead")
                            
                link_index = 0
                for link_index in range(len(link_titles)):
                    link_page = mother.pages[link_titles[link_index]]
                    logging.warning("Deleting %s page, no longer being used\n", link_titles[link_index])
                    link_page.delete()
                
                break
            
            elif replace_all.upper() == 'N': 
                break
            
            else:
                print("\nPlease enter a proper response.")
                replace_all = input("Search the rest of the Wiki for these redirected links? [y/n]: ")
