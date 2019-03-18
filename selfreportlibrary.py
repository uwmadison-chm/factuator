import mwclient
import mwparserfromhell
import logging

def run(mother):
    category = mother.categories['Self Report Measure']
    constructs = {}
    for page in category:
        print("Checking self report", page.name)
        text = page.text()
        p =  mwparserfromhell.parse(text)
        for template in p.filter_templates():
            logging.debug("Page {} has template {} with these params: {}".format(
                page.name, template.name.rstrip(), template.params))
                construct = template.get("Construct").value.rstrip()
                # TODO: Once all of them are categorized, make various listings on the category page by construct, possibly other things

