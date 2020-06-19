import mwclient
import mwparserfromhell
import logging

def run(mother, category_name, matching):
    logging.info(f"Adding category `{category_name}` to pages matching `{matching}`")
    hits = mother.search(matching, what="title")
    for hit in list(hits):
        page = mother.pages[hit.get('title')]
        if not category_name in page.categories() and not page.redirects_to():
            logging.info(f"Adding `{category_name}` to `{page.name}`")
            page.append(f"[[Category:{category_name}]]")

