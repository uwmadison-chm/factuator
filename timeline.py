import mwclient
import mwparserfromhell
import logging
import re
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from collections import defaultdict
from functools import reduce
import operator
import sys

today = datetime.today()
ten_months = relativedelta(months=10)
six_months = relativedelta(months=6)
two_months = relativedelta(months=2)

def color_for_bar_kind(bar_kind):
    if bar_kind == "Planning":
        return '#dae'
    if bar_kind == "Piloting":
        return '#ed8'
    if bar_kind == "Collecting":
        return '#aed'
    if bar_kind == "Writing":
        return '#daa'
    if bar_kind == "Project":
        return '#ade'
    return '#ccc'

def append_rows(normal_rows, truncated_rows, study, bar_kind, s, e):
    color = color_for_bar_kind(bar_kind)

    normal_rows.append("[ '{0}', '{1}', '{2}', new Date({3}, {4}, {5}), new Date({6}, {7}, {8})]".format(
            study, bar_kind, color, s.year, s.month, s.day, e.year, e.month, e.day))

    if e <= today - two_months or s >= today + ten_months:
        return
    if e >= today + ten_months:
        e = today + ten_months
    if s <= today - two_months:
        s = today - two_months

    truncated_rows.append("[ '{0}', '{1}', '{2}', new Date({3}, {4}, {5}), new Date({6}, {7}, {8})]".format(
            study, bar_kind, color, s.year, s.month, s.day, e.year, e.month, e.day))


def build_chart(chart_items, warnings, links=""):
    normal_rows = []
    truncated_rows = []
    for item, dates in chart_items.items():
        bar_added = False
        if dates['Planning Start Date']:
            bar_added = True
            # Could be a project or a study
            if dates['Project Start Date']:
                append_rows(normal_rows, truncated_rows, item,
                        'Planning', dates['Planning Start Date'], dates['Project Start Date'])

            elif dates['Piloting Start Date']:
                append_rows(normal_rows, truncated_rows, item,
                        'Planning', dates['Planning Start Date'], dates['Piloting Start Date'])
            else:
                append_rows(normal_rows, truncated_rows, item,
                        'Planning with No Piloting Start', dates['Planning Start Date'], today + six_months)

        if dates['Project Start Date']:
            bar_added = True
            if dates['Project End Date']:
                append_rows(normal_rows, truncated_rows, item,
                        'Project', dates['Project Start Date'], dates['Project End Date'])
            else:
                append_rows(normal_rows, truncated_rows, item,
                        'Project with No End Date', dates['Project Start Date'], today + six_months)

        if dates['Piloting Start Date']:
            bar_added = True
            if dates['Collecting Start Date']:
                append_rows(normal_rows, truncated_rows, item,
                        'Piloting', dates['Piloting Start Date'], dates['Collecting Start Date'])
            else:
                append_rows(normal_rows, truncated_rows, item,
                        'Piloting with No Collection Start', dates['Piloting Start Date'], today + six_months)

        if dates['Collecting Start Date']:
            bar_added = True
            if dates['End Date']:
                append_rows(normal_rows, truncated_rows, item,
                        'Collecting', dates['Collecting Start Date'], dates['End Date'])
            else:
                append_rows(normal_rows, truncated_rows, item,
                        'Piloting with No Collection Start', dates['Piloting Start Date'], today + six_months)

        # Grants
        if dates['Letter of Intent Due']:
            bar_added = True
            if dates['Submission Date']:
                append_rows(normal_rows, truncated_rows, item,
                        'Writing', dates['Letter of Intent Due'], dates['Submission Date'])
            else:
                append_rows(normal_rows, truncated_rows, item,
                        'Grant with No Submission Date', dates['Letter of Intent Due'], dates['Letter of Intent Due'] + six_months)

        # Default to a boring "Active" bar if we added no specific dates
        if not bar_added and dates['Start Date'] and dates['End Date']:
            append_rows(normal_rows, truncated_rows, item,
                    'Active', dates['Start Date'], dates['End Date'])


    preamble = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>CHM Timelines</title>
<style type="text/css">
body {
  font-family: sans-serif;
  background-color: #eee;
}

.timeline-wrapper {
  overflow-x: scroll;
  overflow-y: scroll;
  width: 100%;
  min-height: 100px;
  border: 1px solid #aaa;
  background-color: #fff;
}

</style>
<script type="text/javascript" src="https://www.gstatic.com/charts/loader.js"></script>
</head>
<body>

""" + links + """

<h1>Near Future</h1>
<div class="timeline-wrapper">
<div id="near-timeline"></div>
</div>

<h1>Entire History</h1>
<div class="timeline-wrapper">
<div id="study-timeline"></div>
</div>

<h5>Date Parsing Warnings</h5>
""" + "<br/>".join(warnings) + """

<script type="text/javascript">
  google.charts.load("current", {packages:["timeline"]});
  google.charts.setOnLoadCallback(drawCharts);
  function drawChart(id, data, width) {
    var container = document.getElementById(id);
    var chart = new google.visualization.Timeline(container);
    var dataTable = new google.visualization.DataTable();
    dataTable.addColumn({ type: 'string', id: 'Role' });
    dataTable.addColumn({ type: 'string', id: 'Name' });
    dataTable.addColumn({ type: 'string', id: 'style', role: 'style' });
    dataTable.addColumn({ type: 'date', id: 'Start' });
    dataTable.addColumn({ type: 'date', id: 'End' });
    dataTable.addRows(data);
    // set a padding value to cover the height of title and axis values
    var paddingHeight = 50;
    // set the height to be covered by the rows
    var rowHeight = dataTable.getNumberOfRows() * 44;
    // set the total chart height
    var chartHeight = rowHeight + paddingHeight;

    chart.draw(dataTable, { width: width, height: chartHeight });
  }
  function drawCharts() {
"""

    ending = """
    drawChart('near-timeline', near, 2000);
    drawChart('study-timeline', all, 2000);
  }
</script>

</body>
</html>
"""

    data1 = "var near = [{}];".format(",\n".join(truncated_rows))
    data2 = "var all = [{}];".format(",\n".join(normal_rows))

    return preamble + data1 + data2 + ending

def fill_hash_dates(warnings, page, template, dates, key):
    if template.has(key):
        d = template.get(key).value.strip()
        if d == "":
            return
        try:
            if re.match(r'^\D{3}', d) is not None:
                pattern = "%B %d, %Y"
            elif re.match(r'^\d{4}', d) is not None:
                pattern = "%Y/%m/%d"
            else:
                pattern = "%m/%d/%Y"
            dates[key] = datetime.strptime(d, pattern)
        except ValueError:
            year = re.match('^[0-9]{4}', d)
            if year is not None:
                year = int(year.group(0))
                warning = "Only found year {} for date {} on page {} from value '{}', guessing January 1".format(year, key, page, d)
                warnings.append(warning)
                logging.warning(warning)
                dates[key] = datetime(year, 1, 1)
            else:
                warning = "Could not get {} for page {} from template value '{}'".format(key, page, d)
                warnings.append(warning)
                logging.warning(warning)


def run(mother):
    to_extract = {
        'Grant': [
            'Letter of Intent Due', 'Submission Date',
        ],
        'Project': [
            'Planning Start Date',
            'Project Start Date', 'Project End Date',
        ],
        'Study': [
            'Start Date', 'End Date',
            'Planning Start Date', 'Piloting Start Date', 'Collecting Start Date',
        ],
    }

    chart_data = {}
    chart_warnings = {}
    def extract(category_name, date_fields):
        logging.info(f"Extracting {date_fields} from Category:{category_name}")
        category = mother.categories[category_name]

        data = {}
        warnings = []
        for page in category:
            thing = page.name
            logging.debug(f"Reading dates from page {thing}")
            text = page.text()
            p = mwparserfromhell.parse(text)

            dates = data[thing] = defaultdict(lambda: False)

            for template in p.filter_templates():
                for field in date_fields:
                    fill_hash_dates(warnings, thing, template, dates, field)
        return data, warnings

    for category_name, fields in to_extract.items():
        chart_data[category_name], chart_warnings[category_name] = \
            extract(category_name, fields)

    # TODO: How to write to wiki when JS is outlawed?
    #chart = mother.pages["CHM Timeline"]
    #oldtext = chart.text()

    # Now we write the chart for each kind
    for category_name, items in chart_data.items():
        with open(f"/home/dfitch/pub_html/timeline/{category_name}.html", "w") as output:
            chart_markup = build_chart(items, chart_warnings[category_name],
                    "<h2><a href='index.html'>Back to all timelines</a></h2>")
            output.write(chart_markup)

    # Join dictionaries
    all_items = {}
    all_items.update(chart_data['Grant'])
    all_items.update(chart_data['Project'])
    all_items.update(chart_data['Study'])

    # And finally the chart of everything joined together
    chart_markup = build_chart(all_items, [],
        "<h2><a href='Grant.html'>View only grants</a> | " +
        "<a href='Project.html'>View only projects</a> | " +
        "<a href='Study.html'>View only studies</a></h2>" +
        "<h2><a href='https://wiki.keck.waisman.wisc.edu/wikis/mother/index.php/Category:Grant'>Wiki grants listing</a> | " +
        "<a href='https://wiki.keck.waisman.wisc.edu/wikis/mother/index.php/Category:Project'>Wiki projects listing</a> | " +
        "<a href='https://wiki.keck.waisman.wisc.edu/wikis/mother/index.php/Category:Study'>Wiki studies listing</a></h2>")
    with open("/home/dfitch/pub_html/timeline/index.html", "w") as output:
        output.write(chart_markup)

