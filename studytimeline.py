import mwclient
import mwparserfromhell
import logging
import re
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
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
    return '#666'

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


def build_chart(studies, warnings):
    normal_rows = []
    truncated_rows = []
    for study, dates in studies.items():
        # ['Start Date', 'End Date', 'Planning Start Date', 'Piloting Start Date', 'Collecting Start Date']
        bar_added = False
        if dates['Planning Start Date']:
            bar_added = True
            if dates['Piloting Start Date']:
                append_rows(normal_rows, truncated_rows, study, 'Planning', dates['Planning Start Date'], dates['Piloting Start Date'])
            else:
                append_rows(normal_rows, truncated_rows, study, 'Planning with No Piloting Start', dates['Planning Start Date'], today + six_months)

        if dates['Piloting Start Date']:
            bar_added = True
            if dates['Collecting Start Date']:
                append_rows(normal_rows, truncated_rows, study, 'Piloting', dates['Piloting Start Date'], dates['Collecting Start Date'])
            else:
                append_rows(normal_rows, truncated_rows, study, 'Piloting with No Collection Start', dates['Piloting Start Date'], today + six_months)

        if dates['Collecting Start Date']:
            bar_added = True
            if dates['End Date']:
                append_rows(normal_rows, truncated_rows, study, 'Collecting', dates['Collecting Start Date'], dates['End Date'])
            else:
                append_rows(normal_rows, truncated_rows, study, 'Piloting with No Collection Start', dates['Piloting Start Date'], today + six_months)

        # Default to a boring "Active" bar if we added no specific dates
        if not bar_added and dates['Start Date'] and dates['End Date']:
            append_rows(normal_rows, truncated_rows, study, 'Active', dates['Start Date'], dates['End Date'])


    preamble = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Study Timelines</title>
<style type="text/css">
body {
  font-face: sans-serif;
  background-color: #eee;
}

.timeline-wrapper {
  overflow-x: scroll;
  overflow-y: scroll;
  width: 100%;
  min-height: 200px;
  border: 1px solid #aaa;
  background-color: #fff;
}

</style>
<script type="text/javascript" src="https://www.gstatic.com/charts/loader.js"></script>
</head>
<body>

<h2>Near Future</h2>
<div class="timeline-wrapper">
<div id="near-timeline"></div>
</div>

<h2>Entire History</h2>
<div class="timeline-wrapper">
<div id="study-timeline"></div>
</div>

<h2>Date Parsing Warnings</h2>
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
    var paddingHeight = 36;
    // set the height to be covered by the rows
    var rowHeight = dataTable.getNumberOfRows() * 36;
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

def fill_hash_dates(warnings, study, template, dates, key):
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
                warning = "Only found year {} for date {} on study {} from value '{}', guessing January 1".format(year, key, study, d)
                warnings.append(warning)
                logging.warning(warning)
                dates[key] = datetime(year, 1, 1)
            else:
                warning = "Could not get {} for study {} from template value '{}'".format(key, study, d)
                warnings.append(warning)
                logging.warning(warning)


def run(mother):
    category = mother.categories['Study']
    date_fields = ['Start Date', 'End Date', 'Planning Start Date', 'Piloting Start Date', 'Collecting Start Date']
    studies = {}
    warnings = []

    for page in category:
        study = page.name
        logging.debug("Reading dates from study", study)
        text = page.text()
        p = mwparserfromhell.parse(text)

        studies[study] = {}
        dates = studies[study]
        for field in date_fields:
            dates[field] = {}

        for template in p.filter_templates():
            for field in date_fields:
                fill_hash_dates(warnings, study, template, dates, field)

    logging.debug("Got dates: ", studies)

    chart = mother.pages["Study Timeline"]
    oldtext = chart.text()
    newtext = build_chart(studies, warnings)
    with open("/home/dfitch/pub_html/study-timeline/index.html", "w") as output:
        output.write(newtext)

    # TODO: How to write to wiki when JS is outlawed?

