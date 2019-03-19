import mwclient
import mwparserfromhell
import logging
import re

def run(mother):
    category = mother.categories['Self Report Measure']
    constructs = {}
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

    logging.debug("Got constructs: ", constructs)

    # Now constructs contains a hash of construct -> list of pages.
    oldtext = category.text()
    cat = mwparserfromhell.parse(oldtext)
    sections = cat.get_sections()
    title = "== Sorted by Construct =="
    newtext = title + "\n\nPlease note: this section is created automatically based on the constructs in each measure's infobox. To edit, go to the measure's page and choose 'Edit with form'.\n\n"

    # Build up an index by construct
    for k in constructs:
        newtext += "===" + k + "===\n"
        for measure in constructs[k]:
            newtext += "* [[" + measure + "]]\n"


    # Replace the "Sorted by Construct" section with our new text
    entirepage = re.sub(title + ".+(?=== Sorted Alpha)", newtext, oldtext)
    print(entirepage)

    # TODO: this should be easy but it's not!
    from IPython import embed
    embed()

    if oldtext != entirepage:
        logging.warning("Updating self-report category page, change detected")
        category.save(entirepage, "Automated edit to build construct categories on self-report library")
