import mwclient
import mwparserfromhell
import logging
import re
from utilities import study_template

def run(mother):
    category = mother.categories['Study']
    all_studies = set()
    status = {}
    has_status = set()
    missing_status = set()
    missing_jarvis = set()

    for page in category:
        logging.debug("Checking study", page.name)
        all_studies.add(page.name)
        text = page.text()
        p = mwparserfromhell.parse(text)
        template = study_template(p)
        if template:
            if template.has("Study Status"):
                s = template.get("Study Status").value.strip()
                if s == "": continue
                words = re.split(r',\s*', s)
                for c in words:
                    status[c] = status.get(c, set())
                    status[c].add(page.name)
                    has_status.add(page.name)

            if not template.has("JARVIS ID") or \
                template.get("JARVIS ID").value.strip() == "":
                missing_jarvis.add(page.name)

        if not page.name in has_status:
            missing_status.add(page.name)

    logging.debug("Got status: ", status)

    # Now statuses contains a hash of construct -> list of pages.
    # NOTE: This re-uses MediaWiki's category CSS classes to get three-column display. Maybe weird to do that?
    oldtext = category.text()
    cat = mwparserfromhell.parse(oldtext)
    sections = cat.get_sections()
    title = "== Sorted by Study Status =="
    newtext = title + "\n\nPlease note: this section is created automatically based on the status in each study's infobox. To edit, go to the study's page and choose 'Edit with form'.\n\n"
    newtext += "<div class='mw-category'>"

    # Build up an index by status
    for k in status:
        newtext += "<div class='mw-category-group'><h3>" + k + "</h3>\n"
        for study in status[k]:
            newtext += "* [[" + study + "]]\n"
        newtext += "</div>"

    # List out things that are missing statuses
    newtext += "<div class='mw-category-group'><h3>No statuses listed</h3>\n"
    for m in missing_status:
        newtext += "* [[" + m + "]]\n"
    newtext += "</div>"

    newtext += "</div>\n\n"

    # Replace the "Sorted by Study Status" section with our new text
    old_section = cat.get_sections(matches = "Sorted by Study Status")[0]
    cat.replace(old_section, newtext)
    newpage = str(cat)

    if oldtext != newpage:
        logging.warning("Updating study category page, change detected")
        category.save(newpage, "Automated edit to build status categories on study library")

    # Now we use the statuses and dates we pulled to edit the "missing Jarvis" and "studies not edited for the longest"

    missing = mother.pages['Studies missing JARVIS IDs']
    oldtext = missing.text()
    newpage = ""
    newpage += "This page is automatically generated.\n\n"
    newpage += "== Pages missing JARVIS IDs ==\n\n"
    for page in sorted(missing_jarvis):
        newpage += f"* [[{page}]]\n"

    if oldtext != newpage:
        logging.warning("Updating missing JARVIS IDs page, change detected")
        missing.save(newpage, "Automated edit")

