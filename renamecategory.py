import mwclient
import mwparserfromhell
import logging
import traceback

def run(mother, old_category_name, new_category_name):
    category = mother.categories[old_category_name]
    for page in category:
        oldtext = page.text()
        newtext = oldtext.replace(f"[[Category:{old_category_name}]]", f"[[Category:{new_category_name}]]")

        if oldtext.strip() != newtext.strip():
            logging.warning(f"Updating page {page.name}, Category:{old_category_name} to Category:{new_category_name}")
            page.save(newtext, f"Automated edit to update Category:{old_category_name} to Category:{new_category_name}")
        else:
            logging.info("Not updating page %s, text identical", page.name)
