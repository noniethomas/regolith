"""Misc. regolith tools.
"""
import email.utils
import os
import platform
import re
import sys
import time
from calendar import monthrange
from copy import copy, deepcopy

from datetime import datetime, date

from regolith.dates import month_to_int, date_to_float
from regolith.sorters import doc_date_key, id_key, ene_date_key, date_key
from regolith.chained_db import ChainDB


try:
    from bibtexparser.bwriter import BibTexWriter
    from bibtexparser.bibdatabase import BibDatabase

    HAVE_BIBTEX_PARSER = True
except ImportError:
    HAVE_BIBTEX_PARSER = False

LATEX_OPTS = ["-halt-on-error", "-file-line-error"]

if sys.version_info[0] >= 3:
    string_types = (str, bytes)
    unicode_type = str
else:
    pass
    # string_types = (str, unicode)
    # unicode_type = unicode

DEFAULT_ENCODING = sys.getdefaultencoding()

ON_WINDOWS = platform.system() == "Windows"
ON_MAC = platform.system() == "Darwin"
ON_LINUX = platform.system() == "Linux"
ON_POSIX = os.name == "posix"


def dbdirname(db, rc):
    """Gets the database dir name."""
    if db.get("local", False) is False:
        dbsdir = os.path.join(rc.builddir, "_dbs")
        dbdir = os.path.join(dbsdir, db["name"])
    else:
        dbdir = db["url"]
    return dbdir


def dbpathname(db, rc):
    """Gets the database path name."""
    dbdir = dbdirname(db, rc)
    dbpath = os.path.join(dbdir, db["path"])
    return dbpath


def fallback(cond, backup):
    """Decorator for returning the object if cond is true and a backup if
    cond is false. """

    def dec(obj):
        return obj if cond else backup

    return dec


def all_docs_from_collection(client, collname, copy=True):
    """Yield all entries in for all collections of a given name in a given
    database. """
    yield from client.all_documents(collname, copy=copy)


SHORT_MONTH_NAMES = (
    None,
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sept",
    "Oct",
    "Nov",
    "Dec",
)


def date_to_rfc822(y, m, d=1):
    """Converts a date to an RFC 822 formatted string."""
    d = datetime(int(y), month_to_int(m), int(d))
    return email.utils.format_datetime(d)


def rfc822now():
    """Creates a string of the current time according to RFC 822."""
    now = datetime.utcnow()
    return email.utils.format_datetime(now)


def gets(seq, key, default=None):
    """Gets a key from every element of a sequence if possible."""
    for x in seq:
        yield x.get(key, default)


def month_and_year(m=None, y=None):
    """Creates a string from month and year data, if available."""
    if y is None:
        return "present"
    if m is None:
        return str(y)
    m = month_to_int(m)
    return "{0} {1}".format(SHORT_MONTH_NAMES[m], y)


def is_since(y, sy, m=1, d=1, sm=1, sd=1):
    """
    tests whether a date is on or since another date

    Parameters
    ----------
    y : int
      the year to be tested
    sy : int
      the since year
    m : int or str
      the month to be tested. Optional, defaults to Jan
    d : int
      the day to be tested.  Defaults to 1
    sm : int or str
      the since month.  Optional, defaults to Jan
    sd: int
      the since day.  Optional, defaults to 1

    Returns
    -------
    True if the target date is the same as, or more recent than, the since date

    """
    s = "{}/{}/{}".format(sd, month_to_int(sm), sy)
    d = "{}/{}/{}".format(d, month_to_int(m), y)
    since = time.mktime(datetime.strptime(s, "%d/%m/%Y").timetuple())
    date = time.mktime(datetime.strptime(d, "%d/%m/%Y").timetuple())
    return since <= date


def is_before(y, by, m=12, d=None, bm=12, bd=None):
    """
    tests whether a date is on or before another date

    Parameters
    ----------
    y : int
      the year to be tested
    by : int
      the before year
    m : int or str
      the month to be tested. Optional, defaults to Dec
    d : int
      the day to be tested.  Defaults to 28
    bm : int or str
      the before month.  Optional, defaults to Dec
    bd: int
      the before day.  Optional, defaults to 28

    Returns
    -------
    True if the target date is the same as, or earlier than, the before date

    """
    if not d:
        d = monthrange(y, month_to_int(m))[1]
    if not bd:
        bd = monthrange(by, month_to_int(bm))[1]
    b = "{}/{}/{}".format(bd, month_to_int(bm), by)
    d = "{}/{}/{}".format(d, month_to_int(m), y)
    before = time.mktime(datetime.strptime(b, "%d/%m/%Y").timetuple())
    date = time.mktime(datetime.strptime(d, "%d/%m/%Y").timetuple())
    return before >= date


def is_between(y, sy, by, m=1, d=1, sm=1, sd=1, bm=12, bd=None):
    """
    tests whether a date is on or between two other dates

    returns true if the target date is between the since date and the before
    date, inclusive.

    Parameters
    ----------
    y : int
      the year to be tested
    sy : int
      the since year
    by : int
      the before year
    m : int or str
      the month to be tested. Optional, defaults to Jan
    d : int
      the day to be tested.  Defaults to 1
    sm : int or str
      the since month.  Optional, defaults to Jan
    bm : int or str
      the before month.  Optional, defaults to Dec
    sd: int
      the since day.  Optional, defaults to 1
    bd: int
      the before day.  Optional, defaults to 28

    Returns
    -------
    True if the target date is between the since date and the before date,
    inclusive (i.e., returns true if the target date is the same as either the
    since date or the before date)

    """

    if not bd:
        bd = monthrange(by, month_to_int(bm))[1]
    return is_since(y, sy, m=m, d=d, sm=sm, sd=sd) and is_before(
        y, by, m=m, d=d, bm=bm, bd=bd
    )


def filter_publications(citations, authors, reverse=False, bold=True,
                        since=None, before=None, ):
    """Filter publications by the author(s)/editor(s)

    Parameters
    ----------
    citations : list of dict
        The publication citations
    authors : set of str
        The authors to be filtered against
    reverse : bool, optional
        If True reverse the order, defaults to False
    bold : bool, optional
        If True put latex bold around the author(s) in question
    """
    pubs = []
    for pub in citations:
        if (
                len((set(pub.get("author", [])) | set(
                    pub.get("editor", []))) & authors)
                == 0
        ):
            continue
        pub = deepcopy(pub)
        if bold:
            bold_self = []
            for a in pub["author"]:
                if a in authors:
                    bold_self.append("\\textbf{" + a + "}")
                else:
                    bold_self.append(a)
            pub["author"] = bold_self
        else:
            pub = deepcopy(pub)
        if since:
            bibdate = date(int(pub.get("year")),
                           month_to_int(pub.get("month", 12)),
                           int(pub.get("day", 28)))
            if bibdate > since:
                if before:
                    if bibdate < before:
                        pubs.append(pub)
                else:
                    pubs.append(pub)
        else:
            pubs.append(pub)

    pubs.sort(key=doc_date_key, reverse=reverse)
    return pubs


def filter_projects(projects, authors, reverse=False):
    """Filter projects by the author(s)

    Parameters
    ----------
    projects : list of dict
        The publication citations
    authors : set of str
        The authors to be filtered against
    reverse : bool, optional
        If True reverse the order, defaults to False
    """
    projs = []
    for proj in projects:
        team_names = set(gets(proj["team"], "name"))
        if len(team_names & authors) == 0:
            continue
        proj = dict(proj)
        proj["team"] = [x for x in proj["team"] if x["name"] in authors]
        projs.append(proj)
    projs.sort(key=id_key, reverse=reverse)
    return projs


def filter_grants(input_grants, names, pi=True, reverse=True, multi_pi=False):
    """Filter grants by those involved

    Parameters
    ----------
    input_grants : list of dict
        The grants to filter
    names : set of str
        The authors to be filtered against
    pi : bool, optional
        If True add the grant amount to that person's total amount
    reverse : bool, optional
        If True reverse the order, defaults to False
    multi_pi : bool, optional
        If True compute sub-awards for multi PI grants, defaults to False
    """
    grants = []
    total_amount = 0.0
    subaward_amount = 0.0
    for grant in input_grants:
        team_names = set(gets(grant["team"], "name"))
        if len(team_names & names) == 0:
            continue
        grant = deepcopy(grant)
        person = [x for x in grant["team"] if x["name"] in names][0]
        if pi:
            if person["position"].lower() == "pi":
                total_amount += grant["amount"]
            else:
                continue
        elif multi_pi:
            grant["subaward_amount"] = person.get("subaward_amount", 0.0)
            grant["multi_pi"] = any(gets(grant["team"], "subaward_amount"))
        else:
            if person["position"].lower() == "pi":
                continue
            else:
                total_amount += grant["amount"]
                subaward_amount += person.get("subaward_amount", 0.0)
                grant["subaward_amount"] = person.get("subaward_amount", 0.0)
                grant["pi"] = [
                    x for x in grant["team"] if x["position"].lower() == "pi"
                ][0]
                grant["me"] = person
        grants.append(grant)
    grants.sort(key=ene_date_key, reverse=reverse)
    return grants, total_amount, subaward_amount


def filter_employment_for_advisees(people, begin_period, status):
    advisees = []
    for p in people:
        for i in p.get("employment", []):
            if i.get("status") == status:
                if i.get("end_year"):
                    end_date = date(i.get("end_year"),
                                    i.get("end_month", 12),
                                    i.get("end_day", 28))
                else:
                    end_date = date.today()
                    i["end_year"] = end_date.year
                if end_date >= begin_period:
                    p['role'] = i.get("position")
                    p['status'] = status
                    p['end_year'] = i.get("end_year", "n/a")
                    advisees.append(p)
    return advisees


def filter_service(ppl, begin_period, type):
    verbose = False
    service = []
    people = copy(ppl)
    for p in people:
        myservice = []
        svc = copy(p.get("service", []))
        for i in svc:
            if i.get("type") == type:
                if i.get('year'):
                    end_year = i.get('year')
                    if verbose: print("end_year from 'year' = {}".format(end_year))
                elif i.get('end_year'):
                    end_year = i.get('end_year')
                    if verbose: print("end_year from 'end_year' = {}".format(end_year))
                else:
                    end_year = date.today().year
                    if verbose: print("no end_year, using today = {}".format(end_year))
                end_date = date(end_year,
                                i.get("end_month", 12),
                                i.get("end_day", 28))
                if verbose: print("end_date = {} and begin_period = {}".format(end_date,begin_period))
                if verbose: print("condition end_date >= begin_period will be used")
                if end_date >= begin_period:
                    if not i.get('month'):
                        month = i.get("begin_month", 0)
                        i['month'] = SHORT_MONTH_NAMES[month_to_int(month)]
                    else:
                        i['month'] = SHORT_MONTH_NAMES[month_to_int(i['month'])]
                    myservice.append(i)
        p['service'] = myservice
        if len(p['service']) > 0:
            service.append(p)
    return service


def filter_facilities(people, begin_period, type, verbose=False):
    facilities = []
    for p in people:
        myfacility = []
        svc = copy(p.get("facilities", []))
        for i in svc:
            if i.get("type") == type:
                if i.get('year'):
                    end_year = i.get('year')
                elif i.get('end_year'):
                    end_year = i.get('end_year')
                else:
                    end_year = date.today().year
                end_date = date(end_year,
                                i.get("end_month", 12),
                                i.get("end_day", 28))
                if end_date >= begin_period:
                    if not i.get('month'):
                        month = i.get("begin_month", 0)
                        i['month'] = SHORT_MONTH_NAMES[month_to_int(month)]
                    else:
                        i['month'] = SHORT_MONTH_NAMES[month_to_int(i['month'])]
                    myfacility.append(i)
        if verbose: print("p['facilities'] = {}".format(myfacility))
        p['facilities'] = myfacility
        if len(p['facilities']) > 0:
            facilities.append(p)
    return facilities


def filter_patents(patentscoll, people, target, since=None, before=None):
    patents = []
    allowed_statuses = ["active", "pending"]
    for i in patentscoll:
        if i.get("status") in allowed_statuses and i.get("type") in "patent":
            inventors = [
                fuzzy_retrieval(
                    people,
                    ["aka", "name", "_id"],
                    inv,
                    case_sensitive=False,
                )
                for inv in i['inventors']
            ]
            person = fuzzy_retrieval(
                people,
                ["aka", "name", "_id"],
                target,
                case_sensitive=False,
            )
            if person in inventors:
                if i.get('end_year'):
                    end_year = i.get('end_year')
                else:
                    end_year = date.today().year
                end_date = date(end_year,
                                i.get("end_month", 12),
                                i.get("end_day", 28))
                if since:
                    if end_date >= since:
                        if not i.get('month'):
                            month = i.get("begin_month", 0)
                            i['month'] = SHORT_MONTH_NAMES[month_to_int(month)]
                        else:
                            i['month'] = SHORT_MONTH_NAMES[
                                month_to_int(i['month'])]

                        events = [event for event in i["events"] if
                                  date(event["year"], event["month"],
                                       event.get("day", 28)) > since]
                        events = sorted(events,
                                        key=lambda event: date(
                                            event["year"],
                                            event["month"],
                                            event.get("day", 28)))
                        i["events"] = events
                        patents.append(i)
                else:
                    events = [event for event in i["events"]]
                    events = sorted(events,
                                    key=lambda event: date(event["year"],
                                                           event["month"],
                                                           28))
                    i["events"] = events
                    patents.append(i)
    return patents


def filter_licenses(patentscoll, people, target, since=None, before=None):
    licenses = []
    allowed_statuses = ["active", "pending"]
    for i in patentscoll:
        if i.get("status") in allowed_statuses and i.get("type") in "license":
            inventors = [
                fuzzy_retrieval(
                    people,
                    ["aka", "name", "_id"],
                    inv,
                    case_sensitive=False,
                )
                for inv in i['inventors']
            ]
            person = fuzzy_retrieval(
                people,
                ["aka", "name", "_id"],
                target,
                case_sensitive=False,
            )
            if person in inventors:
                if i.get('end_year'):
                    end_year = i.get('end_year')
                else:
                    end_year = date.today().year
                end_date = date(end_year,
                                i.get("end_month", 12),
                                i.get("end_day", 28))
                if since:
                    if end_date >= since:
                        if not i.get('month'):
                            month = i.get("begin_month", 0)
                            i['month'] = SHORT_MONTH_NAMES[month_to_int(month)]
                        else:
                            i['month'] = SHORT_MONTH_NAMES[
                                month_to_int(i['month'])]
                        total = sum([event.get("amount") for event in i["events"]])
                        i["total_amount"] = total
                        events = [event for event in i["events"] if
                                  date(event["year"], event["month"],
                                       event.get("day", 28)) > since]
                        events = sorted(events,
                                        key=lambda event: date(event["year"],
                                                               event["month"],
                                                               event.get("day", 28)))
                        i["events"] = events
                        licenses.append(i)
                else:
                    total = sum([event.get("amount") for event in events])
                    i["total_amount"] = total
                    events = [event for event in i["events"]]
                    events = sorted(events,
                                    key=lambda event: date(event["year"],
                                                           event["month"],
                                                           28))
                    i["events"] = events
                    licenses.append(i)

    return licenses


def filter_activities(people, begin_period, type):
    activities = []
    for p in people:
        myactivity = []
        svc = copy(p.get("activities", []))
        for i in svc:
            if i.get("type") == type:
                if i.get('year'):
                    end_year = i.get('year')
                elif i.get('end_year'):
                    end_year = i.get('end_year')
                else:
                    end_year = date.today().year
                end_date = date(end_year,
                                i.get("end_month", 12),
                                i.get("end_day", 28))
                if end_date >= begin_period:
                    if not i.get('month'):
                        month = i.get("begin_month", 0)
                        i['month'] = SHORT_MONTH_NAMES[month_to_int(month)]
                    else:
                        i['month'] = SHORT_MONTH_NAMES[month_to_int(i['month'])]
                    myactivity.append(i)
        p['activities'] = myactivity
        if len(p['activities']) > 0:
            activities.append(p)
    return activities


def filter_presentations(people, presentations, institutions, types=["all"],
                         since=None, before=None, statuses=["accepted"]):
    '''
    filters presentations for different types and date ranges

    Parameters
    ----------
    people: iterable of dicts
      The people collection
    presentations: iterable of dicts
      The presentations collection
    institutions: iterable of dicts
      The institutions collection
    types: list of strings.  Optional, default = all
      The types to filter for.  Allowed types are
        "all",
        "award"
        "plenary"
        "keynote"
        "invited"
        "colloquium"
        "seminar"
        "tutorial"
        "contributed-oral"
        "poster"
    since: date.  Optional, default is None
        The begin date to filter from
    before: date. Optional, default is None
        The end date to filter for.  None does not apply this filter
    statuses: list of str.  Optional. Default is accepted
      The list of statuses to filter for.  Allowed statuses are
        "all"
        "accepted"
        "declined"
        "cancelled"

    Returns
    -------
    list of presentation documents

    '''
    member = "sbillinge"
    presentations = deepcopy(presentations)

    firstclean = list()
    secondclean = list()
    thirdclean = list()
    fourthclean = list()
    presclean = list()

    # build the filtered collection
    # only list the talk if the group member is an author
    for pres in presentations:
        pauthors = pres["authors"]
        if isinstance(pauthors, str):
            pauthors = [pauthors]
        authors = [
            fuzzy_retrieval(
                people,
                ["aka", "name", "_id"],
                author,
                case_sensitive=False,
            )
            for author in pauthors
        ]
        authorids = [
            author["_id"]
            for author in authors
            if author is not None
        ]
        if member in authorids:
            firstclean.append(pres)
    # only list the presentation if it has status in statuses
    for pres in firstclean:
        if pres["status"] in statuses or "all" in statuses:
            secondclean.append(pres)
    # only list the presentation if it has type in types
    for pres in secondclean:
        if pres["type"] in types or "all" in types:
            thirdclean.append(pres)
    # if specified, only list presentations in specified date ranges
    if since:
        for pres in thirdclean:
            presdate = date((pres["begin_year"]),
                            month_to_int(pres["begin_month"]),
                            int(pres["begin_day"]))
            if presdate > since:
                fourthclean.append(pres)
    else:
        fourthclean = thirdclean
    if before:
        for pres in fourthclean:
            presdate = date((pres["begin_year"]),
                            month_to_int(pres["begin_month"]),
                            int(pres["begin_day"]))
            if presdate < before:
                presclean.append(pres)
    else:
        presclean = fourthclean

    # build author list
    for pres in presclean:
        pauthors = pres["authors"]
        if isinstance(pauthors, str):
            pauthors = [pauthors]
        pres["authors"] = [
            author
            if fuzzy_retrieval(
                people,
                ["aka", "name", "_id"],
                author,
                case_sensitive=False,
            )
               is None
            else fuzzy_retrieval(
                people,
                ["aka", "name", "_id"],
                author,
                case_sensitive=False,
            )["name"]
            for author in pauthors
        ]
        authorlist = ", ".join(pres["authors"])
        pres["authors"] = authorlist
        pres["begin_month"] = int(pres["begin_month"])
        pres["date"] = date(
            pres["begin_year"],
            pres["begin_month"],
            pres["begin_day"],
        )
        for day in ["begin_day", "end_day"]:
            pres["{}_suffix".format(day)] = number_suffix(
                pres.get(day, None)
            )
        if "institution" in pres:
            try:
                pres["institution"] = fuzzy_retrieval(
                    institutions,
                    ["aka", "name", "_id"],
                    pres["institution"],
                    case_sensitive=False,
                )
                if pres["institution"] is None:
                    sys.exit(
                        "ERROR: institution {} not found in "
                        "institutions.yml.  Please add and "
                        "rerun".format(pres["institution"])
                    )
            except:
                sys.exit(
                    "ERROR: institution {} not found in "
                    "institutions.yml.  Please add and "
                    "rerun".format(pres["institution"])
                )
            if "department" in pres:
                try:
                    pres["department"] = pres["institution"][
                        "departments"
                    ][pres["department"]]
                except:
                    print(
                        "WARNING: department {} not found in"
                        " {} in institutions.yml.  Pres list will"
                        " build but please check this entry carefully and"
                        " please add the dept to the institution!".format(
                            pres["department"],
                            pres["institution"]["_id"],
                        )
                    )
                    pres["department"] = {
                        "name": pres["department"]
                    }
    if len(presclean) > 0:
        presclean = sorted(
            presclean,
            key=lambda k: k.get("date", None),
            reverse=True,
        )
    return presclean


def awards_grants_honors(p):
    """Make sorted awards grants and honors list.

    Parameters
    ----------
    p : dict
        The person entry
    """
    aghs = []
    if p.get("funding"):
        for x in p.get("funding", ()):
            d = {
                "description": "{0} ({1}{2:,})".format(
                    latex_safe(x["name"]),
                    x.get("currency", "$").replace("$", "\$"),
                    x["value"],
                ),
                "year": x["year"],
                "_key": date_to_float(x["year"], x.get("month", 0)),
            }
            aghs.append(d)
    for x in p.get("service", []) + p.get("honors", []):
        d = {"description": latex_safe(x["name"])}
        if "year" in x:
            d.update(
                {"year": x["year"],
                 "_key": date_to_float(x["year"], x.get("month", 0))}
            )
        elif "begin_year" in x and "end_year" in x:
            d.update(
                {
                    "year": "{}-{}".format(x["begin_year"], x["end_year"]),
                    "_key": date_to_float(x["begin_year"], x.get("month", 0)),
                }
            )
        elif "begin_year" in x:
            d.update(
                {
                    "year": "{}".format(x["begin_year"]),
                    "_key": date_to_float(x["begin_year"], x.get("month", 0)),
                }
            )
        aghs.append(d)
    aghs.sort(key=(lambda x: x.get("_key", 0.0)), reverse=True)
    return aghs


def awards(p, since=None, before=None, ):
    """Make sorted awards and honors

    Parameters
    ----------
    p : dict
        The person entry
    since : date.  Optional, default is None
        The begin date to filter from
    before : date. Optional, default is None
        The end date to filter for.  None does not apply this filter

    """
    if not since: since = date(1500, 1, 1)
    a = []
    for x in p.get("honors", []):
        if "year" in x:
            if date(x.get("year"), 12, 31) > since:
                d = {"description": latex_safe(x["name"]), "year": x["year"],
                     "_key": date_to_float(x["year"], x.get("month", 0))}
                a.append(d)
        elif "begin_year" in x and "end_year" in x:
            if date(x.get("begin_year", 12, 31)) > since:
                d = {"description": latex_safe(x["name"]),
                     "year": "{}-{}".format(x["begin_year"], x["end_year"]),
                     "_key": date_to_float(x["begin_year"], x.get("month", 0)),
                     }
                a.append(d)
        elif "begin_year" in x:
            if date(x.get("begin_year"), 12, 31) > since:
                d = {"description": latex_safe(x["name"]),
                     "year": "{}".format(x["begin_year"]),
                     "_key": date_to_float(x["begin_year"], x.get("month", 0)),
                     }
                a.append(d)
    a.sort(key=(lambda x: x.get("_key", 0.0)), reverse=True)
    return a


HTTP_RE = re.compile(
    r"https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{2,256}\.[a-z]{2,4}\b([-a-zA-Z0-9@:%_\+.~#?&//=]*)"
)


def latex_safe_url(s):
    """Makes a string that is a URL latex safe."""
    return s.replace("#", r"\#")


def latex_safe(s, url_check=True, wrapper="url"):
    """Make string latex safe

    Parameters
    ----------
    s : str
    url_check : bool, optional
        If True check for URLs and wrap them, if False check for URL but don't
        wrap, defaults to True
    wrapper : str, optional
        The wrapper for wrapping urls defaults to url
    """
    if not s:
        return s
    if url_check:
        # If it looks like a URL make it a latex URL
        url_search = HTTP_RE.search(s)
        if url_search:
            url = r"{start}\{wrapper}{{{s}}}{end}".format(
                start=(latex_safe(s[: url_search.start()])),
                end=(latex_safe(s[url_search.end():])),
                wrapper=wrapper,
                s=latex_safe_url(s[url_search.start(): url_search.end()]),
            )
            return url
    return (
        s.replace("&", r"\&")
            .replace("$", r"\$")
            .replace("#", r"\#")
            .replace("_", r"\_")
    )


def make_bibtex_file(pubs, pid, person_dir="."):
    """Make a bibtex file given the publications

    Parameters
    ----------
    pubs : list of dict
        The publications
    pid : str
        The person id
    person_dir : str, optional
        The person's directory
    """
    if not HAVE_BIBTEX_PARSER:
        return None
    skip_keys = {"ID", "ENTRYTYPE", "author"}
    bibdb = BibDatabase()
    bibwriter = BibTexWriter()
    bibdb.entries = ents = []
    for pub in pubs:
        ent = dict(pub)
        ent["ID"] = ent.pop("_id")
        ent["ENTRYTYPE"] = ent.pop("entrytype")
        for n in ["author", "editor"]:
            if n in ent:
                ent[n] = " and ".join(ent[n])
        for key in ent.keys():
            if key in skip_keys:
                continue
            # don't think I want the bibfile entries to be latex safe
            # ent[key] = latex_safe(ent[key])
            ent[key] = str(ent[key])
        ents.append(ent)
    fname = os.path.join(person_dir, pid) + ".bib"
    with open(fname, "w", encoding="utf-8") as f:
        f.write(bibwriter.write(bibdb))
    return fname


def document_by_value(documents, address, value):
    """Get a specific document by one of its values

    Parameters
    ----------
    documents: generator
        Generator which yields the documents
    address: str or tuple
        The address of the data in the document
    value: any
        The expected value for the document

    Returns
    -------
    dict:
        The first document which matches the request
    """
    if isinstance(address, str):
        address = (address,)
    for g_doc in documents:
        doc = deepcopy(g_doc)
        for add in address:
            doc = doc[add]
        if doc == value:
            return g_doc


def fuzzy_retrieval(documents, sources, value, case_sensitive=True):
    """Retrieve a document from the documents where value is compared against
    multiple potential sources

    Parameters
    ----------
    documents: generator
        The documents
    sources: iterable
        The potential data sources
    value:
        The value to compare against to find the document of interest
    case_sensitive: Bool
        When true will match case (Default = True)

    Returns
    -------
    dict:
        The document

    Examples
    --------
    >>> fuzzy_retrieval(people, ['aka', 'name'], 'pi_name', case_sensitive = False)

    This would get the person entry for which either the alias or the name was
    ``pi_name``.

    """
    for doc in documents:
        returns = []
        for k in sources:
            ret = doc.get(k, [])
            if not isinstance(ret, list):
                ret = [ret]
            returns.extend(ret)
        if not case_sensitive:
            returns = [reti.lower() for reti in returns if
                       isinstance(reti, str)]
            if isinstance(value, str):
                if value.lower() in frozenset(returns):
                    return doc
        else:
            if value in frozenset(returns):
                return doc


def number_suffix(number):
    """returns the suffix that adjectivises a number (st, nd, rd, th)

    Paramters
    ---------
    number: integer
        The number.  If number is not an integer, returns an empty string

    Returns
    -------
    suffix: string
        The suffix (st, nd, rd, th)
    """
    if not isinstance(number, (int, float)):
        return ""
    if 10 < number < 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return suffix


def dereference_institution(input_record, institutions):
    """Tool for replacing placeholders for institutions with the actual
    institution data. Note that the replacement is done inplace

    Parameters
    ----------
    input_record : dict
        The record to dereference
    institutions : iterable of dicts
        The institutions
    """
    inst = input_record.get("institution") or input_record.get("organization")
    db_inst = fuzzy_retrieval(institutions, ["name", "_id", "aka"], inst)
    if db_inst:
        input_record["institution"] = db_inst["name"]
        input_record["organization"] = db_inst["name"]
        if db_inst.get("country") == "USA":
            state_country = db_inst.get("state")
        else:
            state_country = db_inst.get("country")
        input_record["location"] = "{}, {}".format(db_inst["city"],
                                                   state_country)
        if "department" in input_record:
            input_record["department"] = fuzzy_retrieval(
                [db_inst["departments"]], ["name", "aka"],
                input_record["department"]
            )

def merge_collections(a, b, target_id):
    """
    merge two collections into a single merged collection

    for keys that are in both collections, the value in b will be kept

    Parameters
    ----------
    a  the inferior collection (will lose values of shared keys)
    b  the superior collection (will keep values of shared keys)
    target_id  str  the name of the key used in b to dereference ids in a

    Returns
    -------
    the combined collection.  Note that it returns a collection only containing
    merged items from a and b that are dereferenced in b, i.e., the merged
    intercept.  If you want the union you can update the returned collection
    with a.

    Examples
    --------
    >>>  grants = merge_collections(self.gtx["proposals"], self.gtx["grants"], "proposal_id")

    This would merge all entries in the proposals collection with entries in the
    grants collection for which "_id" in proposals has the value of
    "proposal_id" in grants.
    """
    adict = {}
    for k in a:
        adict[k.get("_id")] = k
    bdict = {}
    for k in b:
        bdict[k.get("_id")] = k

    b_for_a = {}
    for k in adict:
        for kk, v in bdict.items():
            if v.get(target_id, "") == k:
                b_for_a[k] = kk
    chained = {}
    for k, v in b_for_a.items():
        chained[k] = ChainDB(adict[k],
                             bdict[v])
    return list(chained.values())


def get_dates(thing):
    '''
    given a dict like thing, return the items

    Parameters
    ----------
    thing: dict
      the dict that contains the dates

    Returns
    -------
       dict containing begin day, begin month, begin year, end day, end month, end year
    '''
    dateitems = ['begin_day', 'begin_month', 'begin_year', 'end_day',
                 'end_month',
                 'end_year', 'day', 'month', 'year']
    dates = [thing.get(item) for item in dateitems]
    dateout = {}
    [dateout.update({item: date}) for item, date in zip(dateitems, dates) if
     date]
    print(dateout)
    return dateout
def merge_collections(a, b, target_id):
    """
    merge two collections into a single merged collection

    for keys that are in both collections, the value in b will be kept

    Parameters
    ----------
    a  the inferior collection (will lose values of shared keys)
    b  the superior collection (will keep values of shared keys)
    target_id  str  the name of the key used in b to dereference ids in a

    Returns
    -------
    the combined collection.  Note that it returns a collection only containing
    merged items from a and b that are dereferenced in b, i.e., the merged
    intercept.  If you want the union you can update the returned collection
    with a.

    Examples
    --------
    >>>  grants = merge_collections(self.gtx["proposals"], self.gtx["grants"], "proposal_id")

    This would merge all entries in the proposals collection with entries in the
    grants collection for which "_id" in proposals has the value of
    "proposal_id" in grants.
    """
    adict = {}
    for k in a:
        adict[k.get("_id")] = k
    bdict = {}
    for k in b:
        bdict[k.get("_id")] = k

    b_for_a = {}
    for k in adict:
        for kk, v in bdict.items():
            if v.get(target_id, "") == k:
                b_for_a[k] = kk
    chained = {}
    for k, v in b_for_a.items():
        chained[k] = ChainDB(adict[k],
                             bdict[v])
    return list(chained.values())


if __name__ == "__main__":
    test = get_dates(
        {'begin_day': 1, 'begin_month': 1, 'begin_year': 2000, 'end_day': 1,
         'end_month': 1,
         'end_year': 2001, 'month': 1, 'year': 2003})
