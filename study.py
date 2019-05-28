import mwclient
import mwparserfromhell
import logging
import requests
import dateutil.parser
import traceback
from jarvis import Jarvis

def jsondate_to_str(j):
    return str(dateutil.parser.parse(j).date())

def run(mother):
    category = mother.categories['Study']
    for page in category:
        oldtext = page.text()
        p =  mwparserfromhell.parse(oldtext)
        for template in p.filter_templates(matches="Study"):
            logging.debug("Page {} has template {} with these params: {}".format(
                page.name, template.name.rstrip(), template.params))

            try:
                jarvis_id = template.get("JARVIS ID").value.rstrip()
            except ValueError:
                # Skip JARVIS integration if there's no id
                logging.warning("No JARVIS ID on study page %s" % page.name)
                pass
            else:
                try:
                    # Pull stuff out of JARVIS and put it into the template params
                    j = Jarvis()

                    logging.info("JARVIS id for %s is %s" % (page.name, jarvis_id))
                    irb_exp = j.irb_expirations(jarvis_id)
                    if irb_exp:
                        template.add("JARVIS IRB Expiration", irb_exp)
                    quota = j.total_active_quota(jarvis_id)
                    if quota:
                        template.add("JARVIS Study Drive Quota", quota)
                    
                    # Personnel is a different section of the document, so replace that
                    personnel = j.personnel(jarvis_id)
                    old_sections = p.get_sections(matches = "JARVIS Personnel")
                    if len(old_sections) > 0:
                        old_personnel = old_sections[0]
                        p.replace(old_personnel, personnel)

                except Exception as e:
                    # Print the error and keep going
                    logging.error(f"Problem fetching from JARVIS on study page {page.name}: {traceback.print_exc()}")
                    pass

            try:
                nih_id = template.get("NIH RePORTER ID").value.rstrip()
            except ValueError:
                # We just skip NIH integration if there's no id or we fail in any way
                logging.warning("No NIH ID on study page %s" % page.name)
                pass
            else:
                # award date, NIH start / end dates, break out official NIH title
                logging.info("NIH id for %s is %s" % (page.name, nih_id))
                nih_url = "https://api.federalreporter.nih.gov/v1/Projects?nihApplId=" + nih_id
                resp = requests.get(nih_url)

                if resp.status_code != 200:
                    logging.warning("GET {} {}".format(nih_url, resp.status_code))
                else:
                    data = resp.json()
                    template.add("NIH Title", data['title'])
                    template.add("NIH Fiscal Year", data['fy'])
                    template.add("NIH Budget Start Date", jsondate_to_str(data['budgetStartDate']))
                    template.add("NIH Budget End Date", jsondate_to_str(data['budgetEndDate']))
                    template.add("NIH Project Start Date", jsondate_to_str(data['projectStartDate']))
                    template.add("NIH Project End Date", jsondate_to_str(data['projectEndDate']))

        newtext = str(p)
        newtext = newtext.replace("<noinclude>NOTE: This is prefab content inserted in new study pages</noinclude>", "")

        if oldtext != newtext:
            logging.warning("Updating study page %s, change detected", page.name)
            page.save(newtext, "Automated edit to update study values from JARVIS and NIH")
        else:
            logging.info("Not updating study page %s, text identical", page.name)
