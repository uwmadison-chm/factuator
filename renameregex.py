import mwclient
import mwparserfromhell
import logging
import re

def run(mother, matching, regex, replacement):
    logging.info(f"Renaming pages matching `{matching}` replacing `{regex}` with `{replacement}`")
    hits = mother.search(matching, what="title")
    for hit in list(hits):
        page = mother.pages[hit.get('title')]
        if page.redirects_to():
            continue
        name = page.name
        regex = re.compile(regex)
        new_name = regex.sub(replacement, name)
        if name != new_name:
            logging.info(f"Renaming `{name}` to `{new_name}`")
            # Check for a redirect or existing page at new name
            existing_page = mother.pages[new_name]
            if existing_page:
                if existing_page.redirects_to():
                    existing_page.delete()
                else:
                    logging.warning(f"Could not rename, there is already a page at `{new_name}`")
            page.move(new_name)

