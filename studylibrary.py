import mwclient
import mwparserfromhell
import logging
import re

def run(mother):
    category = mother.categories['Study']
    status = {}
    has_status = []
    missing_status = []
    for page in category:
        logging.debug("Checking study", page.name)
        text = page.text()
        p = mwparserfromhell.parse(text)
        for template in p.filter_templates():
            if template.has("Study Status"):
                s = template.get("Study Status").value.strip()
                if s == "": continue
                words = re.split(r',\s*', s)
                for c in words:
                    status[c] = status.get(c, [])
                    status[c].append(page.name)
                    has_status.append(page.name)

        if not page.name in has_status:
            missing_status.append(page.name)

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
