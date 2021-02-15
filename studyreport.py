import mwclient
import mwparserfromhell
import logging
import re
import csv
from utilities import study_template

def fetch(page, template, key):
    thing = ""
    try:
        thing = template.get(key).value.rstrip()
    except ValueError:
        logging.warning(f"No '{key}' on study page {page.name}")
        pass
    return thing

def run(mother):
    category = mother.categories['Study']

    with open('studyreport.csv', 'w') as csvfile:
        writer = csv.writer(csvfile)
        columns = [
            "Study",
            "AKA",
            "Short Description",
            "Study Status",
            "Active",
            "In Quarterly Progress Report",
            "Verified for Progress Report Date",
            "Funded Fully or Partially Through RSP",
            "CHM Website",
            "Start Date",
            "End Date",
            "Planning Start Date",
            "Piloting Start Date",
            "Collecting Start Date",
            "Projected Enrollment",
            "Current Enrollment",
            "IRB Number",
            "Grant Number",
            "Funding Source",
            "ARROW URL",
            "NIH RePORTER ID",
            "ClinicalTrials.Gov",
            "JARVIS ID",
            "PIs",
            "Project Manager",
            "Current Contact",
            "Project Links",
            ]

        writer.writerow(columns)
        for page in category:
            logging.debug("Loading study", page.name)
            text = page.text()
            p = mwparserfromhell.parse(text)

            template = study_template(p)
            column_values = [fetch(page, template, x) for x in columns]
            column_values[0] = page.name

            writer.writerow(column_values)

