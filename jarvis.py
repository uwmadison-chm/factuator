import psycopg2
import psycopg2.extras

# NOTE: You will need to `kinit` a kerberos token to make this db connection work

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
        # And now we also want groups

        group_info = self.select("""SELECT concat(p.first, ' ', p.last), ag.name FROM irb_studies s
            JOIN irb_protocols irb ON s.irb_protocol_id = irb.id
            JOIN irb_protocol_acgroups ipa ON irb.id = ipa.irb_protocol_id
            JOIN account_groups ag on ipa.acgroup_id = ag.id
            JOIN account_group_members gm on gm.group_id = ag.id
            JOIN account_groups ag2 on ag2.id = gm.member_id
            JOIN people p on ag2.person_id = p.id
            WHERE NOT ag2.isgroup AND p.first IS NOT NULL AND p.first != '' AND study_id = %s
            ORDER BY ag.id ASC, p.last ASC, p.first ASC""" % study_id)

        group_map = {}
        all_groups = []
        people_map = {}
        all_people = []

        for p in self.people(study_id):
            name = "{first} {last}".format(**p)
            if not name in all_people:
                all_people.append(name)
            people_map[name] = p

        for x in group_info:
            name = x[0]
            group = x[1]
            if not name in all_people:
                all_people.append(name)
            if not group in all_groups:
                all_groups.append(group)
            if name in group_map:
                group_map[name].append(group)
            else:
                group_map[name] = [group]

        table = """{| class="wikitable" style="text-align:left;"\n!Name\n!PI\n!Admin"""
        for g in all_groups:
            table += "\n!" + g

        for name in all_people:
            table += "\n|-\n"
            table += "\n|"

            if name in people_map:
                p = people_map[name]
                table += "'''" + name + "'''"
                
                table += "\n|"
                if p['pi']:
                    table += "✓"

                table += "\n|"
                if p['admin']:
                    table += "✓"

            else:
                table += name
                table += "\n|"
                table += "\n|"

            for g in all_groups:
                table += "\n|"
                if name in group_map:
                    if g in group_map[name]:
                        table += "✓"

        table += "\n|}"


        title = "=== JARVIS Personnel ==="
        link = """This information is auto-populated from [https://brainimaging.waisman.wisc.edu/members/jarvis/studies/{} JARVIS].""".format(study_id)
        return title + "\n\n" + link + "\n\n" + table

