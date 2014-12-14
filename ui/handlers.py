from flask import request
from mongoutils.memex_mongo_utils import MemexMongoUtils
from scrapyutils.scrapydutil import ScrapydJob
from settings import SCREENSHOT_DIR
from mongoutils.known_hosts import KnownHostsCompare
from mongoutils.validate import validate_url
from ranker.rescore_mongo import train_and_score_mongo

def get_screenshot_relative_path(real_path):
    try:
        return real_path.split("static/")[1]
    except IndexError:
        return None

def request_wants_json():

    best = request.accept_mimetypes \
        .best_match(['application/json', 'text/html'])
    return best == 'application/json' and \
        request.accept_mimetypes[best] > \
        request.accept_mimetypes['text/html']

def hosts_handler(page = 1, which_collection = "crawl-data", filter_field = None, filter_regex = None):
    """Put together host documents for use with hosts endpoint """

    mmu = MemexMongoUtils(which_collection = which_collection)
    for host in mmu.get_hosts_filtered(filter_field = "host", filter_regex = "windows"):
        print "b"
        print host
    
    khc = KnownHostsCompare()

    host_dics = mmu.list_hosts(page = page, filter_field = filter_field, filter_regex = filter_regex)

    for host_dic in host_dics:

        print host_dic
        #host scoring is added here as is known hostedness
        host_dic.pop("_id")
        is_known_host = khc.is_known_host(host_dic["host"])
        host_dic["is_known_host"] = is_known_host
        hsu = mmu.get_highest_scoring_url_with_screenshot(host_dic["host"])
        #host_score = mmu.get_host_score(host_dic["host"])
        #host_dic["host_score"] = host_score

        if hsu:
            screenshot_path = get_screenshot_relative_path(hsu['screenshot_path'])
            host_dic["hsu_screenshot_path"] = screenshot_path
        else:
            host_dic["hsu_screenshot_path"] = None

    return host_dics

def urls_handler(host = None, which_collection  = "crawl-data"):
    """Put together host documents for use with hosts endpoint """

    mmu = MemexMongoUtils(which_collection = which_collection)
    url_dics = mmu.list_urls(host = host, limit = 1000)

    for url_dic in url_dics:
        url_dic.pop("_id")
        date = url_dic["crawled_at"]
        try:
            url_dic["crawled_at"] = date.strftime("%Y-%m-%d %H:%M:%S")
        except:
            url_dic["crawled_at"] = str(date)

    return url_dics

def schedule_spider_handler(seed, spider_host = "localhost", spider_port = "6800"):

    mmu = MemexMongoUtils()
    scrapyd_util = ScrapydJob(spider_host, spider_port, project = "discovery-project", screenshot_dir = SCREENSHOT_DIR)
    job_id = scrapyd_util.schedule(seed)
    mmu.add_job(seed, job_id, project = "discovery-project", spider = "website_finder")

    return True

def add_known_urls_handler(urls_raw):

    mmu = MemexMongoUtils(which_collection = "known-data")
    for url in urls_raw.splitlines():
        validate_url(url)
        try:
            mmu.insert_url(url = url)
        except:
            print "Existing URL attempted to be uploaded, skipping it..."


def get_job_state_handler(url, spider_host = "localhost", spider_port = "6800"):

    mmu = MemexMongoUtils()
    seed_doc = mmu.get_seed_doc(url)
    job_id = seed_doc["job_id"]
    project = seed_doc["project"]

    scrapyd_util = ScrapydJob(spider_host, spider_port, project = project)

    return scrapyd_util.get_state(job_id)

def discovery_handler():

    mmu = MemexMongoUtils()
    seeds = mmu.list_seeds()
    return seeds

def mark_interest_handler(interest, url):

    mmu = MemexMongoUtils()
    if interest:
        mmu.set_interest(url, True)

    else:
        #if user marks url as uninteresting, score drops to 0
        mmu.set_interest(url, False)

        #!should we be doing this?
#        mmu.set_score(url, 0)

def set_score_handler(url, score):
    mmu = MemexMongoUtils()
    mmu.set_score(url, score)

##workspace    
############# TAGS #############

def list_tags(host):
    mmu = MemexMongoUtils()
    return mmu.list_tags(host)


def save_tags(host, tags):
    mmu = MemexMongoUtils()
    mmu.save_tags(host, tags)

def search_tags(term):
    mmu = MemexMongoUtils()
    return mmu.search_tags(term)

############# Display Hosts #############

def save_display(host, displayable):
    mmu = MemexMongoUtils()
    if not bool(displayable):
        for url_doc in mmu.list_urls(host = host, limit=100000000):
            mmu.set_interest(url_doc["url"], False)

    else:

        for url_doc in mmu.list_urls(host = host, limit=100000000):
            mmu.set_interest(url_doc["url"], True)

    return mmu.save_display(host, displayable)

############# Workspaces #############

##workspace
def list_workspace():
    mmu = MemexMongoUtils()
    return mmu.list_workspace()

def add_workspace(name):
    mmu = MemexMongoUtils()
    mmu.add_workspace(name)

def set_workspace_selected(id):
    mmu = MemexMongoUtils()
    mmu.set_workspace_selected(id)

def delete_workspace(id):
    mmu = MemexMongoUtils()
    mmu.delete_workspace(id)

##keyword
def list_keyword():
    mmu = MemexMongoUtils()
    return mmu.list_keyword()

def save_keyword(list):
    mmu = MemexMongoUtils()
    mmu.save_keyword(list)

##searchTerm
def list_search_term():
    mmu = MemexMongoUtils()
    return mmu.list_search_term()

def save_search_term(list):
    mmu = MemexMongoUtils()
    mmu.save_search_term(list)

##ranking/scoring
def schedule_spider_searchengine_handler(search_terms, spider_host="localhost", spider_port="6800"):
    mmu = MemexMongoUtils()
    project = "searchengine-project"
    spider = "google.com"
    scrapyd_util = ScrapydJob(
        scrapyd_host=spider_host,
        scrapyd_port=spider_port,
        project=project,
        spider=spider,
        screenshot_dir=SCREENSHOT_DIR,
    )
    job_id = scrapyd_util.schedule_keywords(search_terms)
    mmu.add_job(search_terms, job_id, project=project, spider=spider)

def get_score_handler():

    mmu = MemexMongoUtils()
    yes_interest_docs = mmu.list_all_urls_with_interest(True, return_html = True)
    no_interest_docs = mmu.list_all_urls_with_interest(False, return_html = True)
    return yes_interest_docs, no_interest_docs

def rescore_db_handler():

    train_and_score_mongo()

if __name__ == "__main__":

    print hosts_handler(filter_field = "host", filter_regex=".*")
    
    
    