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

    def protocols(self, study_id):
        return self.select("SELECT protocol, expiration FROM irb_protocols p JOIN irb_studies s ON p.id = s.irb_protocol_id WHERE s.study_id = %s" % study_id)


#from IPython import embed; embed()
