"""Date based tools"""

import datetime as dt
import calendar

MONTHS = {
    "jan": 1,
    "jan.": 1,
    "january": 1,
    "feb": 2,
    "feb.": 2,
    "february": 2,
    "mar": 3,
    "mar.": 3,
    "march": 3,
    "apr": 4,
    "apr.": 4,
    "april": 4,
    "may": 5,
    "may.": 5,
    "jun": 6,
    "jun.": 6,
    "june": 6,
    "jul": 7,
    "jul.": 7,
    "july": 7,
    "aug": 8,
    "aug.": 8,
    "august": 8,
    "sep": 9,
    "sep.": 9,
    "sept": 9,
    "sept.": 9,
    "september": 9,
    "oct": 10,
    "oct.": 10,
    "october": 10,
    "nov": 11,
    "nov.": 11,
    "november": 11,
    "dec": 12,
    "dec.": 12,
    "december": 12,
    "": 1,
}


def month_to_int(m):
    """Converts a month to an integer."""
    try:
        m = int(m)
    except ValueError:
        m = MONTHS[m.lower()]
    return m


def date_to_float(y, m, d=0):
    """Converts years / months / days to a float, eg 2015.0818 is August
    18th 2015. """
    y = int(y)
    m = month_to_int(m)
    d = int(d)
    return y + (m / 100.0) + (d / 10000.0)


def begin_end_date(doc):
    '''returns the beginning amd ending date from a document as date objects

    Assumes, for example, regolith standard, that begin date info is in keys
    "begin_year", "begin_month" and "begin_day".

    Currently, keys have to be at the top level of the document

    Parameters
    ----------
    doc
      The document from which we want to extract the beginning and ending date

    Returns
    -------
       The begin and end-date as datetime.date object
    '''
    by = str(doc.get('begin_year'))
    bm = str(month_to_int(doc.get('begin_month')))
    bd = str(doc.get('begin_day', 1))
    ey = doc.get('end_year')
    em = month_to_int(doc.get('end_month'))
    month_last_day = calendar.monthrange(ey, em)[1]
    ed = str(doc.get('end_day', month_last_day))
    startdate = dt.datetime.strptime(by + bm + bd,
                                     '%Y%m%d').date()
    enddate = dt.datetime.strptime(str(ey) + str(em) + ed,
                                   '%Y%m%d').date()
    return startdate, enddate
