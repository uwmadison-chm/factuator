import argparse
import logging
import coloredlogs

import mwclient
import mwparserfromhell

import auth_store

parser = argparse.ArgumentParser(description='Automate the wiki.')
parser.add_argument('-v', '--verbose', action='count')
parser.add_argument('-s', '--study', help='Update study pages', action='store_true')
parser.add_argument('--selfreport', help='Create initial self report pages (DO NOT RUN, for one-time use)', action='store_true')
parser.add_argument('--selfreportlibrary', help='Update self report library', action='store_true')
parser.add_argument('--medialinks-category', help='Update File: to Media: links in given category', action='append')
parser.add_argument('--medialinks-page', help='Update File: to Media: links on given page', action='append')
parser.add_argument('--redirectlinks-page', help='Update redirected links in given pages', action='append')
parser.add_argument('--studylibrary', help='Update study library', action='store_true')
parser.add_argument('--studyimporter', metavar="CSV", help='Create study pages from given tsv')
parser.add_argument('--timeline', help='Create or update timeline page based on Category:Study, Category:Project, and Category:Grant', action='store_true')
parser.add_argument('--studyreport', help='Generate CSV report about studies', action='store_true')
parser.add_argument('--rename-category', nargs=2, help='Rename category arg1 to arg2')
parser.add_argument('-a', '--all', help='Run all known automated updates', action='store_true')
args = parser.parse_args()

if args.verbose:
    if args.verbose > 1:
        coloredlogs.install(level='DEBUG')
    elif args.verbose > 0:
        coloredlogs.install(level='INFO')
else:
    coloredlogs.install(level='WARN')

auth = auth_store.get_auth()
user = auth[0]

ua = 'factuator/0.1 run by User:' + user
mother = mwclient.Site(('https', 'wiki.keck.waisman.wisc.edu'), path='/wikis/mother/', httpauth=auth)

if args.study:
    import study
    study.run(mother)
elif args.selfreport:
    import selfreport
    selfreport.run(mother)
elif args.selfreportlibrary:
    import selfreportlibrary
    selfreportlibrary.run(mother)
elif args.medialinks_category:
    import medialinks
    medialinks.run_categories(mother, args.medialinks_category)
elif args.medialinks_page:
    import medialinks
    medialinks.run_pages(mother, args.medialinks_page)
elif args.redirectlinks_page:
    import redirectlinks
    redirectlinks.run_pages(mother, args.redirectlinks_page)
elif args.studyimporter:
    import studyimporter
    studyimporter.run(mother, args.studyimporter)
elif args.studylibrary:
    import studylibrary
    studylibrary.run(mother)
elif args.timeline:
    import timeline
    timeline.run(mother)
elif args.studyreport:
    import studyreport
    studyreport.run(mother)
elif args.rename_category:
    import renamecategory
    renamecategory.run(mother, args.rename_category[0], args.rename_category[1])
elif args.all:
    import study
    study.run(mother)
    import studylibrary
    studylibrary.run(mother)
    import selfreportlibrary
    selfreportlibrary.run(mother)
    import timeline
    timeline.run(mother)
else:
    parser.print_help()
