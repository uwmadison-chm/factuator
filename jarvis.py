import psycopg2
import psycopg2.extras

# NOTE: You will need to `kinit` a kerberos token to make this db connection work

# Jarvis tables:
#
# ['account_group_members',
#  'account_groups',
#  'account_requests',
#  'activity_logs',
#  'ar_internal_metadata',
#  'budget_categories',
#  'computer_group_members',
#  'computer_part_instances',
#  'computer_part_types',
#  'computer_parts',
#  'computer_statuses',
#  'computer_tickets',
#  'computers',
#  'drives',
#  'funds',
#  'irb_people',
#  'irb_protocol_acgroups',
#  'irb_protocols',
#  'irb_studies',
#  'ksus',
#  'labs',
#  'lib_checkouts',
#  'lib_items',
#  'lib_media',
#  'license_types',
#  'net_bind_forwards',
#  'net_bind_rec_types',
#  'net_if_jacks',
#  'net_ifs',
#  'net_ips',
#  'net_jacks',
#  'net_subnets',
#  'operating_systems',
#  'people',
#  'person_email_aliases',
#  'program_installs',
#  'program_purchases',
#  'programs',
#  'quotas',
#  'roles',
#  'rooms',
#  'schema_migrations',
#  'sessions',
#  'storage_requests',
#  'studies',
#  'switch_ports',
#  'switches',
#  'ticket_message_parts',
#  'ticket_messages',
#  'ticket_statuses',
#  'tickets',
#  'titles',
#  'unix_shells']

class Jarvis:
    def __init__(self):
        self.db = psycopg2.connect("postgresql://togarashi.keck.waisman.wisc.edu/bi?krbsrvname=postgres")

    def select(self, x):
        cursor = self.db.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute(x)
        return cursor.fetchall()

    def select_list(self, x):
        cursor = self.db.cursor()
        cursor.execute(x)
        return cursor.fetchall()

    def columns(self, table):
        return self.select_list("select COLUMN_NAME from information_schema.COLUMNS where TABLE_NAME = '%s'" % table)

    def tables(self):
        return self.select("select relname from pg_class where relkind='r' and relname !~ '^(pg_|sql_)';")

    def study(self, study_id):
        return self.select("SELECT folder, name, current_subjects, total_subjects FROM studies WHERE id = %s" % study_id)


    def quotas(self, study_id):
        return self.select("SELECT * FROM quotas where startdate < current_date AND enddate > current_date AND study_id = %s" % study_id)

    def total_active_quota(self, study_id):
        return "{}gb".format(sum([quota['quotagb'] for quota in self.quotas(study_id)]))


    def protocols(self, study_id):
        return self.select("SELECT protocol, expiration FROM irb_protocols p JOIN irb_studies s ON p.id = s.irb_protocol_id WHERE s.study_id = %s" % study_id)

    def irb_expirations(self, study_id):
        irbs = self.protocols(study_id)
        if len(irbs) == 1:
            return str(irbs[0][1])
        else:
            return ", ".join(["{} expires {}".format(p[0], p[1]) for p in irbs])


    def people(self, study_id):
        return self.select("""SELECT p.id, p.first, p.last, ip.pi, ip.admin, ip.irb_alerts FROM irb_studies s
                JOIN irb_people ip ON ip.irb_protocol_id = s.irb_protocol_id
                JOIN people p on p.id = ip.person_id
                WHERE s.study_id = %s
                ORDER BY ip.pi DESC, ip.admin DESC, ip.irb_alerts DESC, ip.created_at ASC""" % study_id)

    def personnel(self, study_id):
        # We want a table of people and whether they are a PI, admin, and/or irb_alert_thinger
        table = """{| class="wikitable" style="text-align:left;"\n!Name\n!PI\n!Admin\n!IRB Alerts"""
        for p in self.people(study_id):
            table += "\n|-\n"
            table += "\n|{first} {last}".format(**p)

            table += "\n|"
            if p['pi']:
                table += "✓"

            table += "\n|"
            if p['admin']:
                table += "✓"

            table += "\n|"
            if p['irb_alerts']:
                table += "✓"

        table += "\n|}"

        title = "=== JARVIS Personnel ==="
        link = """This information is auto-populated from [https://brainimaging.waisman.wisc.edu/members/jarvis/studies/{} JARVIS].""".format(study_id)
        return title + "\n\n" + link + "\n\n" + table


