import mwclient
import mwparserfromhell
import logging
import re
from utilities import study_template
from jarvis import Jarvis

def run(mother):
    category = mother.categories['Study']
    all_studies = set()
    status = {}
    has_status = set()
    missing_status = set()
    missing_jarvis = set()
    jarvis_ids = set()

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
            else:
                jarvis_ids.add(int(template.get("JARVIS ID").value.strip()))

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
    # Sort by certain rules
    sort_order = [
        "In Development", "Piloting", "Collecting", "Data Collection Complete", 
        "Analyzing", "Publishing", "IRB Closed"]
    for k in sort_order:
        if not k in status:
            continue
        newtext += "<div class='mw-category-group'><h3>" + k + "</h3>\n"
        for study in sorted(list(status[k])):
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
    missing = mother.pages['Study pages missing JARVIS IDs']
    oldtext = missing.text()
    newpage = "This page is automatically generated. See also [[JARVIS IDs missing study pages]]\n\n"
    newpage += "== Pages missing JARVIS IDs ==\n\n"
    for page in sorted(missing_jarvis):
        newpage += f"* [[{page}]]\n"

    if oldtext != newpage:
        logging.warning("Updating missing JARVIS IDs page, change detected")
        missing.save(newpage, "Automated edit")

    # Now we build the opposite thing
    missing = mother.pages['JARVIS IDs missing study pages']
    oldtext = missing.text()
    newpage = "This page is automatically generated and only includes more recent entries in JARVIS. See also [[Study pages missing JARVIS IDs]]\n\n"
    newpage += "== JARVIS IDs missing study pages ==\n\n"

    j = Jarvis()
    all_studies = j.select("SELECT id, folder, name, created_at FROM studies ORDER BY created_at DESC LIMIT 30")
    for s in all_studies:
        jarvis_id, folder, name, created_at = s
        if not jarvis_id in jarvis_ids:
            newpage += f"* ID {jarvis_id} in /study/{folder}: \"{name}\" (created at {created_at})\n"

    if oldtext != newpage:
        logging.warning("Updating missing study pages page, change detected")
        missing.save(newpage, "Automated edit")

