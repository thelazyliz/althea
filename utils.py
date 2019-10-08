def prettify_position(obj):
    # assign column names first
    rows = ['\t'.join(obj[0].keys())]
    # then add the rows
    for item in obj:
        rows.extend(['\t'.join(item.values())])
    obj_string = '\n'.join(rows)
    return obj_string