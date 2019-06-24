import mwclient
import mwparserfromhell
import logging
import sys
import re

def newtext(name, content):
    return """
{{Self Report Measure
|Name=%s
|Reference=
|Duration=
|Cost=
|License terms=
|Constructs=
|Studies using measure=
}}
==Author's Description==

TODO

==Brief Description for Publications==

TODO: Here is the text you would paste in grants, papers, IRB protocols, and so on.

==Sample questions==

TODO

==Materials==
%s

==Psychometrics==

==Discussion==

===Internal Findings===

===Publications With Relevant Findings===


{{RSC.css}}
[[Category:Self Report Measure]]
    """ % (name, content)

def run(mother):
    library = mother.pages["Self-Report Library"]
    p = mwparserfromhell.parse(library.text())
    for link in p.filter_wikilinks():
        if "[[:Category" in link: continue
        title = str(link.title).replace("_", " ")
        page = mother.pages[title]
        if page.exists:
            measure = mwparserfromhell.parse(page.text())

            if "[[Category:Self Report Measure]]" in measure: continue
            if "#REDIRECT" in measure: continue

            logging.info("Updating page", title)

            # trim out link to Self-Report Library, not needed in category mode
            for measure_link in measure.filter_wikilinks():
                if "Library" in measure_link.title \
                    and "Self" in measure_link.title \
                    and "Report" in measure_link.title:
                    measure.remove(measure_link)

            # Fix whitespace
            trimmed = re.sub("\n{2,}", str(measure), "\n\n").strip()

            output = newtext(title, trimmed)
            page.save(output, "Automated edit to move self reports into category")


