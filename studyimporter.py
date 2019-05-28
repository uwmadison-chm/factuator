import mwclient
import mwparserfromhell
import logging
import csv
import sys

def importer(mother, row, boilerplate):
    title = row["Study Short Name"]
    logging.info("Importing %s" % title)

    page = mother.pages[title]
    oldtext = page.text()
    if oldtext != "":
        logging.warning("Collision on study page %s" % title)
        return
        
    p = mwparserfromhell.parse(oldtext)

    p.insert(0, boilerplate)
    p.insert(0, "{{Study}}")

    template = p.filter_templates(matches="Study")[0]
    template.add("AKA", row["AKA"])
    template.add("PIs", row["PIs"])
    template.add("Project Manager", row["Project Manager"])
    template.add("Current Contact", row["Current Contact"])
    template.add("Short Description", row["Short Description"])
    template.add("Website", row["Website"])
    template.add("Start Date", row["Start Date"])
    template.add("End Date", row["End Date"])
    template.add("Projected Enrollment", row["Projected Enrollment"])
    template.add("Current Enrollment", row["Current Enrollment"])
    template.add("Study Status", row["Study Status"])
    template.add("IRB Number", row["IRB Number"])
    template.add("Grant Number", row["Grant Number"])
    template.add("Funding Source", row["Funding Source"])
    template.add("ARROW URL", row["ARROW URL"])
    template.add("Study Drive Name", row["Study Drive Name"])
    if row["ClinicalTrials.Gov URL"] != "N/A":
        template.add("ClinicalTrials.Gov", row["ClinicalTrials.Gov URL"])

    # insert into page at top section
    overview = row["General Overview Paragraph"]
    if overview not in p:
        p.insert(0, overview)

    newtext = str(p)
    if oldtext != newtext:
        page.save(newtext, "Automated edit to create page from metadata")

def run(mother, csvpath):
    logging.info("Opening %s" % csvpath)
    with open(csvpath) as csvfile:
        reader = csv.DictReader(csvfile, delimiter='\t')
        boilerplate = mother.pages['Template:Study boilerplate'].text()
        for row in reader:
            importer(mother, row, boilerplate)
