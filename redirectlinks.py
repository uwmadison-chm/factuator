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
        print(page.name, "links to empty redirect page, fixing link...\n" )
        red = p.filter_wikilinks()
        has_bad_link = True
        for link in red:
            red_link = link.title
    return red_link, has_bad_link
              
def run_pages(mother, pages):
    for title in pages:
        page = mother.pages[title]
        oldtext = page.text()
        p =  mwparserfromhell.parse(oldtext)
        link_titles = []
        
        #Replaces links to redirected pages with proper link
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
            
       
        #Optional: Look for same redirect pages on entire MOTHER wiki. Replaces appropriate links and deleting redirect pages when no longer being used
        if len(link_titles) > 0 :
            logging.warning("Scanning entire wiki will take a few minutes")
            replace_all = input("Search the rest of the Wiki for these redirected links? [y/n]:")
            while (len(replace_all) >= 1):
                if replace_all.upper() == 'Y':
                    for page in mother.pages:
                        link_index = 0
                        logging.debug("Searching ", page.name)
                        oldpage = page.text()
                        p =  mwparserfromhell.parse(oldpage)
                        for link in p.filter_wikilinks():
                            for link_index in range(len(link_titles)):
                                if link.title == (link_titles[link_index]):
                                    p.replace(link.title, red_link)
                                    link_index += 1 
                        newpage = str(p)
        
                        if oldpage != newpage:
                            logging.warning("\nUpdating %s page, change detected", page.name)
                            page.save(newpage, "Automated edit to make links to redirected pages link to proper page instead")
                   
                    link_index = 0
                    for link_index in range(len(link_titles)):
                        link_page = mother.pages[link_titles[link_index]]
                        logging.warning("\nDeleting %s page, no longer being used", link_titles[link_index])
                        link_page.delete()
                   
                    break
               
                elif replace_all.upper() == 'N': 
                    break
               
                else:
                    print("\nPlease enter a proper response.")
                    replace_all = input("Search the rest of the Wiki for these redirected links? [y/n]: ")
