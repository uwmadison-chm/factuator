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
parser.add_argument('--redirectlinks-category', help='Update redirected links in category')
parser.add_argument('--studylibrary', help='Update study library', action='store_true')
parser.add_argument('--studyimporter', metavar="CSV", help='Create study pages from given tsv')
parser.add_argument('--timeline', help='Create or update timeline page based on Category:Study, Category:Project, and Category:Grant', action='store_true')
parser.add_argument('--studyreport', help='Generate CSV report about studies', action='store_true')
parser.add_argument('--add-category', nargs=2, metavar=('category', 'match'), help='Add category `category` to pages with `match` in the title')
parser.add_argument('--rename-category', nargs=2, metavar=('old', 'new'), help='Rename category `old` to `new`')
parser.add_argument('--rename-regex', nargs=3, metavar=('match', 'regex', 'result'), help='Rename all pages with `match` in the title replacing `regex` with `result`')
parser.add_argument('--export-gdoc', nargs=5, metavar=('wiki_prefix', 'file_prefix', 'http_prefix', 'drive_id', 'unsorted_folder_id'), help='Export wiki with `wiki_prefix` to google drive at `drive_id` creating unsorted folders in `unsorted_folder_id` for eventual gdocwiki use where `file_prefix` allows public-internet-visible viewing of files at `http_prefix` [EXPERIMENTAL]')
parser.add_argument('--export-gdoc-single', nargs=6, metavar=('wiki_prefix', 'file_prefix', 'http_prefix', 'drive_id', 'unsorted_folder_id', 'page_title'), help='Export single wiki page with `wiki_prefix` to google drive at `drive_id` creating unsorted folders in `unsorted_folder_id` for eventual gdocwiki use where `file_prefix` allows public-internet-visible viewing of files at `http_prefix` [EXPERIMENTAL]')
parser.add_argument('--link-gdoc', nargs=4, metavar=('file_prefix', 'drive_id', 'files_folder_id', 'folder_id'), help='Walk folder with `folder_id` and repair links based on stored mappings [EXPERIMENTAL]')
parser.add_argument('--link-gdoc-single', nargs=4, metavar=('file_prefix', 'drive_id', 'files_folder_id', 'doc_id'), help='Repair links in doc based on stored mappings [EXPERIMENTAL]')
parser.add_argument('-f', '--force', help='Force whatever changes instead of trying to be precise about updates', action='store_true')
parser.add_argument('-n', '--older', metavar="ISO_DATE", help='Update pages not updated since a given date')
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
mother = mwclient.Site('wiki.keck.waisman.wisc.edu', path='/wikis/mother/', httpauth=auth)

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
elif args.redirectlinks_category:
    import redirectlinks
    redirectlinks.run_category(mother, args.redirectlinks_category)
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
elif args.add_category:
    import addcategory
    addcategory.run(mother, args.add_category[0], args.add_category[1])
elif args.rename_category:
    import renamecategory
    renamecategory.run(mother, args.rename_category[0], args.rename_category[1])
elif args.rename_regex:
    import renameregex
    renameregex.run(mother, args.rename_regex[0], args.rename_regex[1], args.rename_regex[2])
elif args.all:
    import study
    study.run(mother)
    import studylibrary
    studylibrary.run(mother)
    import selfreportlibrary
    selfreportlibrary.run(mother)
    import timeline
    timeline.run(mother)
elif args.export_gdoc:
    import gdocdriver
    gdocdriver.export_mediawiki(mother, args.export_gdoc[0],
            args.force, args.older,
            args.export_gdoc[1], args.export_gdoc[2],
            args.export_gdoc[3], args.export_gdoc[4])
elif args.export_gdoc_single:
    import gdocdriver
    gdocdriver.export_mediawiki(mother, args.export_gdoc_single[0],
            args.force, args.older,
            args.export_gdoc_single[1], args.export_gdoc_single[2],
            args.export_gdoc_single[3], args.export_gdoc_single[4],
            args.export_gdoc_single[5])
elif args.link_gdoc:
    import gdocdriver
    gdocdriver.link_folder(mother, args.link_gdoc[0], args.link_gdoc[1],
            args.link_gdoc[2], args.link_gdoc[3])
elif args.link_gdoc_single:
    import gdocdriver
    gdocdriver.link_doc(mother, args.link_gdoc_single[0], args.link_gdoc_single[1], 
            args.link_gdoc_single[2], args.link_gdoc_single[3])
else:
    parser.print_help()
