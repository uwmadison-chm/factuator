
def study_template(p):
    study_regex = r"Study"
    for template in p.filter_templates(matches=study_regex):
        if template.name.strip() == study_regex:
            return template
    return None
