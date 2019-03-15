import mwclient
import mwparserfromhell
import logging

def run(mother):
    category = mother.categories['Study']
    for page in category:
        text = page.text()
        p =  mwparserfromhell.parse(text)
        for template in p.filter_templates():
            logging.debug("Page {} has template {} with these params: {}".format(
                page.name, template.name.rstrip(), template.params))
            try:
                jarvis_id = template.get("JARVIS ID").value.rstrip()
            except ValueError:
                # We just skip JARVIS integration if there's no id or we fail in any way
                logging.warning("No JARVIS ID on study page %s" % page.name)
                pass
            else:
                # TODO: Pull stuff out of JARVIS and put it into the template params
                logging.info("JARVIS id for %s is %s" % (page.name, jarvis_id))
                template.add("JARVIS IRB Expiration", "[from JARVIS TODO]")
                template.add("JARVIS Study Drive Quota", "[from JARVIS TODO]")
                template.add("JARVIS Personnel", "[from JARVIS TODO]")
                newtext = str(p)

