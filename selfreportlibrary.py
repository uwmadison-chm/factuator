import mwclient
import mwparserfromhell
import logging
import re

# Adds cost, duration, and item info to construct list for each measure 
def details(mpage):
    mtext = mpage.text()
    mp = mwparserfromhell.parse(mtext)
    cost = ""
    duration = ""
    items = ""
    for template in mp.filter_templates():
        if template.has("Cost"):
            cost = template.get("Cost").value.strip()
            if '[' in cost:
                url = re.findall(r'(https?://\S+)', cost)
                cost = "[" + url[0] + "]"
                if ".pdf" in url[0]:
                    cost = "[" + url[0]
            if cost != "":
                cost = "Cost: " + cost
        if template.has("Duration"):
            duration = template.get("Duration").value.strip()
            if duration != "":
                duration = "Duration: " + duration
        if template.has("Number of items"):
            items = template.get("Number of items").value.strip()
            if items != "":
                items = "Items: " + items
        info = [cost, duration, items]
        inf = [value for value in info if value]
        return inf
    return []
    

def run(mother):
    category = mother.categories['Self Report Measure']
    constructs = {}
    has_constructs = []
    missing_constructs = []
    for page in category:
        logging.debug("Checking self report", page.name)
        text = page.text()
        p = mwparserfromhell.parse(text)
        for template in p.filter_templates():
            if template.has("Constructs"):
                s = template.get("Constructs").value.strip()
                if s == "": continue
                words = re.split(r',\s*', s)
                for c in words:
                    constructs[c] = constructs.get(c, [])
                    constructs[c].append(page.name)
                    has_constructs.append(page.name)

        if not page.name in has_constructs:
            missing_constructs.append(page.name)

    logging.debug("Got constructs: ", constructs)

    # Now constructs contains a hash of construct -> list of pages.
    # NOTE: This re-uses MediaWiki's category CSS classes to get three-column display. Maybe weird to do that?
    oldtext = category.text()
    cat = mwparserfromhell.parse(oldtext)
    sections = cat.get_sections()
    title = "== Sorted by Construct =="
    newtext = title + "\n\nPlease note: this section is created automatically based on the constructs in each measure's infobox. To edit, go to the measure's page and choose 'Edit with form'.\n\n"
    newtext += "<div class='mw-category'>"

    # Build up an index by construct
    for k in sorted(constructs.keys()):
        newtext += "<div class='mw-category-group'><h3>" + k + "</h3>\n"
        for measure in constructs[k]:
            mpage = mother.pages[measure]
            inf = details(mpage)
            # Only add measure info if it exists in page template
            if inf != []:
                newtext += "* [[" + measure + "]] - (" + ", ".join(inf) + ")\n"
            else :
                newtext += "* [[" + measure + "]]\n"
        newtext += "</div>"
        
    # List out things that are missing constructs
    newtext += "<div class='mw-category-group'><h3>No constructs listed</h3>\n"
    for m in missing_constructs:
        mpage = mother.pages[m]
        inf = details(mpage)
        # Only add measure info if it exists in page template
        if inf != []:
            newtext += "* [[" + m + "]] - (" + ", ".join(inf) + ")\n"
        else:
            newtext += "* [[" + m + "]]\n"
    newtext += "</div>"

    newtext += "</div>\n\n"
    
    # Replace the "Sorted by Construct" section with our new text
    old_section = cat.get_sections(matches = "Sorted by Construct")[0]
    cat.replace(old_section, newtext)
    newpage = str(cat)

    if oldtext != newpage:
        logging.warning("Updating self-report category page, change detected")
        category.save(newpage, "Automated edit to build construct categories on self-report library")
