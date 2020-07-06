import mwclient
import mwparserfromhell
import logging
import re

def run(mother, matching, regex, replacement):
    logging.info(f"Renaming pages matching `{matching}` replacing `{regex}` with `{replacement}`")
    hits = mother.search(matching, what="title")
    matcher = re.compile(matching)
    for hit in list(hits):
        title = hit.get('title')
        if not matcher.match(title):
            logging.debug(f"Skipping hit {title}")
            continue
        logging.info(f"Checking page {title}")
        page = mother.pages[title]
        # NOTE: Checking page.redirects_to was throwing API errors.
        if "#REDIRECT" in page.text():
            continue
        logging.info(f"Page is not a redirect")
        name = page.name
        regex = re.compile(regex)
        new_name = regex.sub(replacement, name)
        if name != new_name:
            logging.info(f"Renaming `{name}` to `{new_name}`")
            # Check for a redirect or existing page at new name
            existing_page = mother.pages[new_name]
            if existing_page:
                if "#REDIRECT" in existing_page.text():
                    logging.warning(f"Deleting existing redirect at `{new_name}`")
                    existing_page.delete()
                else:
                    logging.warning(f"Could not rename, there is already a page at `{new_name}`")
            page.move(new_name)

