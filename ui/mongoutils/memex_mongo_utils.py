import itertools
import csv
import pymongo
from pymongo import MongoClient
import traceback
import json
from random import randrange
from operator import itemgetter
from urlparse import urlparse
from pymongo.errors import DuplicateKeyError
from bson.objectid import ObjectId
from errors import DeletingSelectedWorkspaceError
from ui.utils.url import extract_tld
import re

class MemexMongoUtils(object):

    def __init__(self, init_db=False, address="mongodb", port=27017, which_collection="crawl-data"):
        """This class  initializes a Memex Mongo object and rebuilds the db collections if you want.

        Warning: init_db will delete your collection when set to True

        which_collection specifies whether to connect to the scrapy crawl data or common crawl data collection
        to connect to common crawl specify this as cc-crawldata
        """

        self.client = MongoClient(address, port)
        
        db = self.client["MemexHack"]

        workspace_collection_name = "workspace"
        self.workspace_collection = db[workspace_collection_name]

        seed_collection_name = "seedinfo"
        cf_collection_name = "cfinfo"

        if which_collection == "cc-crawl-data":
            url_collection_name = "cc-urlinfo"
            host_collection_name = "cc-hostinfo"
        elif which_collection == "known-data":
            url_collection_name = "known-urlsinfo"
            host_collection_name = "known-hostsinfo"
        elif which_collection == "crawl-data":
            # Search for the current selected workspace
            # if empty leave the default
            ws_doc = self.workspace_collection.find_one({"selected" : True})
            if None == ws_doc:
                url_collection_name = "urlinfo"
                host_collection_name = "hostinfo"
            else:
                url_collection_name = "urlinfo" + "-" + ws_doc['name']
                host_collection_name = "hostinfo" + "-" + ws_doc['name']
                seed_collection_name = "seedinfo" + "-" + ws_doc['name']
                cf_collection_name = "cfinfo" + "-" + ws_doc['name']
        else:
            raise Exception("You have specified an invalid collection, please choose either crawl-data or cc-crawl-data for which_collection")

        self.urlinfo_collection = db[url_collection_name]
        self.hostinfo_collection = db[host_collection_name]
        self.seed_collection = db[seed_collection_name]
        self.cf_collection = db[cf_collection_name]

        if init_db:
            print "Got call to initialize db with %s %s" % (url_collection_name, host_collection_name)
            try:
                print "Dropping %s and %s" % (url_collection_name, host_collection_name)
                db.drop_collection(url_collection_name)
                db.drop_collection(host_collection_name)
                db.drop_collection(seed_collection_name)
                db.drop_collection(cf_collection_name)

            except:
                print "handled:"
                traceback.print_exc()

            db.create_collection(url_collection_name)
            db.create_collection(host_collection_name)
            db.create_collection(seed_collection_name)
            db.create_collection(cf_collection_name)

            # create index and drop any dupes
            self.urlinfo_collection.ensure_index("url", unique=True, drop_dups=True)
            self.hostinfo_collection.ensure_index("host", unique=True, drop_dups=True)
            self.seed_collection.ensure_index("url", unique=True, drop_dups=True)
            self.hostinfo_collection.ensure_index("host_score")
            self.cf_collection.ensure_index("meta.fingerprint", unique=True, drop_dups=True)
            self.cf_collection.ensure_index("score")

    def init_workspace(self, address="mongodb", port=27017):
        db = self.client["MemexHack"]
        workspace_collection_name = "workspace"
        self.workspace_collection = db[workspace_collection_name]
        res = self.workspace_collection.find();
        docs = list(res)
        for doc in docs:
            self.delete_workspace_related(doc['name'])
        
        print "Dropping %s" % (workspace_collection_name)
        db.drop_collection(workspace_collection_name)
        db.create_collection(workspace_collection_name)
        self.add_workspace("default")
        self.set_workspace_selected_by_name("default")
        
    def list_indexes(self):
        
        return self.hostinfo_collection.index_information()

    def list_urls(self, host=None, limit=20):

        if not host:
            docs = self.urlinfo_collection.find({ "display": { "$ne": 0 } }).sort("score", -1).limit(limit)
        else:
            docs = self.urlinfo_collection.find({"host" : host}).sort("score", -1).limit(limit)

        return list(docs)

    def list_hosts(self, page=1, page_size=10, filter_regex = None, filter_field = None, show_all=None):

        if filter_regex and filter_field:
            docs = self.get_hosts_filtered(filter_field = filter_field, filter_regex = filter_regex, show_all=show_all)
        else:
            docs = self.get_hosts(show_all=show_all)

        try:
            docs = docs.skip(page_size * (page - 1)).limit(page_size)
        except Exception:
            docs = docs.limit(page_size)

        docs_list = list(docs.limit(page_size))

        return docs_list

    def list_all_hosts(self):
        #docs = self.hostinfo_collection.find({ "display": { "$ne": 0 } })
        docs = self.get_hosts()
        return list(docs)

    def list_all_urls(self, sort_by="host", return_html = False, list_deleted = False):

        if list_deleted:
            docs = self.urlinfo_collection.find({}, {'html':int(return_html), 'html_rendered': int(return_html)})  # .sort(sort_by, 1)
        else:
            docs = self.urlinfo_collection.find({ "display": { "$ne": 0 } }, {'html':int(return_html), 'html_rendered': int(return_html)})  # .sort(sort_by, 1)

        return sorted(list(docs), key=lambda rec: rec[sort_by])
    
    def list_all_urls_iterator(self, return_html):
        
        docs = self.urlinfo_collection.find({}, {'url':int(True), 'html':int(return_html), 'html_rendered': int(return_html)})  # .sort(sort_by, 1)
        return docs        

    def list_all_urls_with_interest(self, interest, return_html = False):

        docs = self.urlinfo_collection.find({"interest": interest}, {"html": int(return_html)})
        return list(docs)

    def list_seeds(self, sort_by="url"):

        docs = self.seed_collection.find().sort(sort_by, 1)

        return list(docs)

    def __insert_url_test_data(self, test_fn="test_sites.csv"):

        with open(test_fn) as testfile:
            reader = csv.DictReader(testfile)

            # insert url data
            for url_dic in reader:
                try:
                    if not "score" in url_dic:
                        url_dic["score"] = randrange(100)

                    self.urlinfo_collection.save(url_dic)

                except:
                    print url_dic
                    traceback.print_exc()
                    # doc with same url exists, skip
                    pass

    def insert_url(self, **kwargs):
        '''
        Inserts a URL and properly increments the needed host document. If URL already exists, it will be skipped.
        
        is_seed,crawled_at,title,url,link_url,link_text,html_rendered,referrer_depth,depth,total_depth,host,referrer_url,html        
        '''

        url = kwargs["url"]
        extracted = extract_tld(url)
        host = extracted.domain + '.' + extracted.suffix

        url_doc = kwargs
        url_doc["host"] = host
        
        try:
            self.urlinfo_collection.save(kwargs)
        except DuplicateKeyError:
            pass

        host_doc = {"host" : host, "num_urls" : 1, "host_score" : None}

        #try to insert a new host doc, if fail increment url count
        try:
            self.hostinfo_collection.save(host_doc)
        except DuplicateKeyError:
            self.hostinfo_collection.update({"host" : host}, {"$inc" : {"num_urls" : 1}})

    def get_host_score(self, host):

        high_score_doc = self.urlinfo_collection.find_one({"host" : host}, sort = [("score", -1)])
        if "score" in high_score_doc:
            return high_score_doc["score"]
        else:
            return 0

    def insert_test_data(self, test_fn="test_sites.csv"):

        self.__insert_url_test_data(test_fn=test_fn)

    def add_job(self, url, job_id, project, spider, default_state="Initializing"):

        try:
            seed_doc = {"url" : url, "state" : default_state, "job_id" : job_id, "project" : project, "spider" : spider}
            self.seed_collection.save(seed_doc)
        except Exception:
            self.seed_collection.update({"url" : url}, {'$set' : {"job_id" : job_id}})

    def list_seed_docs(self):
        return list(self.seed_collection.find())        

    def mark_seed_state(self, url, state):

        self.seed_collection.update({"url" : url}, {'$set': {'state': state}})

    def get_highest_scoring_url_with_screenshot(self, host):

        docs = list(self.urlinfo_collection.find({'$and' : [{'screenshot_path' : {"$exists" : "true"}}, {'host' : host}]}))
        for doc in docs:
            if not "score" in doc:
                doc["score"] = 0

        urls_sorted = sorted(docs, key=itemgetter('score'), reverse=True)

        if urls_sorted:
            return urls_sorted[0]
        else:
            return None

    def get_seed_doc(self, url):

        seed_doc = self.seed_collection.find_one({"url" : url})
        return seed_doc

    def set_interest(self, url, interest):

        self.urlinfo_collection.update({"url" : url}, {'$set' : {"interest" : interest}})

    def set_score(self, url, score_set):

        self.urlinfo_collection.update({"url" : url}, {'$set' : {"score" : score_set}})

    def set_host_score(self, host, score_set):

        self.hostinfo_collection.update({"host" : host}, {'$set' : {"host_score" : score_set}})
        
    def set_screenshot_path(self, url, screenshot_path):

        self.urlinfo_collection.update({"url" : url}, {'$set' : {"screenshot_path" : screenshot_path}})        

    def set_html_rendered(self, url, html_rendered):

        self.urlinfo_collection.update({"url" : url}, {'$set' : {"html_rendered" : html_rendered}})

    def delete_urls_by_match(self, match, negative_match = False):
        """Remove hosts and urls by matching URLs"""

        url_dics = self.list_all_urls()
        for url_dic in url_dics:
            if negative_match:
                if not match in url_dic["url"]:                    
                    self.hostinfo_collection.remove({"host" : url_dic["host"]})
                    self.urlinfo_collection.remove({"url" : url_dic["url"]})
            else:
                if match in url_dic["url"]:
                    self.hostinfo_collection.remove({"host" : url_dic["host"]})
                    self.urlinfo_collection.remove({"url" : url_dic["url"]})

    def delete_hosts_by_match(self, match, negative_match = False):
        """Remove hosts and urls by matching hosts"""

        host_dics = self.list_all_hosts()
        for host_dic in host_dics:
            if negative_match:
                if not match in host_dic["host"]:                    
                    self.hostinfo_collection.remove({"host" : host_dic["host"]})
                    self.urlinfo_collection.remove({"host" : host_dic["host"]})
            else:
                if match in host_dic["host"]:
                    self.hostinfo_collection.remove({"host" : host_dic["host"]})
                    self.urlinfo_collection.remove({"host" : host_dic["host"]})

    def delete_all_by_match(self, match, negative_match = False):
        """Remove hosts and urls by matching both urls and hosts"""

        self.delete_urls_by_match(match, negative_match = negative_match)
        self.delete_hosts_by_match(match, negative_match = negative_match)

    #####################   workspace  #####################

    def list_workspace(self):
        docs = self.workspace_collection.find()
        return list(docs)

    def add_workspace(self, name):
        self.workspace_collection.save({'name':name, 'selected': False})

        url_collection_name = "urlinfo" + "-" + name
        host_collection_name = "hostinfo" + "-" + name
        seed_collection_name = "seedinfo" + "-" + name
        cf_collection_name = "cfinfo" + "-" + name

        db = self.client["MemexHack"]
        db.create_collection(url_collection_name)
        db.create_collection(host_collection_name)
        db.create_collection(seed_collection_name)
        db.create_collection(cf_collection_name)

        # create index and drop any dupes
        db[url_collection_name].ensure_index("url", unique=True, drop_dups=True)
        db[host_collection_name].ensure_index("host", unique=True, drop_dups=True)
        db[seed_collection_name].ensure_index("url", unique=True, drop_dups=True)
        db[cf_collection_name].ensure_index("meta.fingerprint", unique=True, drop_dups=True)

    def get_workspace_by_id(self,id):
        return self.workspace_collection.find_one({"_id" : ObjectId( id )})
        
    def set_workspace_selected_by_name(self, name):
        self.workspace_collection.update({}, {'$set' : {"selected" : False}}, multi=True)
        self.workspace_collection.update({"name" : name}, {'$set' : {"selected" : True}})

    def set_workspace_selected(self, id):
        self.workspace_collection.update({}, {'$set' : {"selected" : False}}, multi=True)
        self.workspace_collection.update({"_id" : ObjectId( id )}, {'$set' : {"selected" : True}})

    def get_workspace_selected(self):
        return self.workspace_collection.find_one({"selected" : True})

    def delete_workspace(self, id):
        ws_doc = self.workspace_collection.find_one({"_id" : ObjectId( id )})
        if ws_doc["selected"] == True:
            raise DeletingSelectedWorkspaceError('Deleting the selected workspace is not allowed')
        else:
            self.delete_workspace_related(ws_doc['name'])
            self.workspace_collection.remove({"_id" : ObjectId( id )})

    def delete_workspace_related(self,name):
        db = self.client["MemexHack"]
        print "Dropping %s" % ("urlinfo" + "-" + name)
        db["urlinfo" + "-" + name].drop()
        print "Dropping %s" % ("hostinfo" + "-" + name)
        db["hostinfo" + "-" + name].drop()
        print "Dropping %s" % ("seedinfo" + "-" + name)
        db["seedinfo" + "-" + name].drop()
        print "Dropping %s" % ("cfinfo" + "-" + name)
        db["cfinfo" + "-" + name].drop()

    #####################   keyword  #####################
    def list_keyword(self):
        ws = self.get_workspace_selected()

        if ws == None or "keyword" not in ws or ws["keyword"] == None:
            return []
        else:
            return list(ws["keyword"])

    def save_keyword(self, keywords):
        ws = self.get_workspace_selected()
        if ws == None:
            self.workspace_collection.upsert({"_id" : "_default"}, {'$set' : {"keyword" : keywords}})
        else:
            self.workspace_collection.update({"_id" : ObjectId(ws["_id"] )}, {'$set' : {"keyword" : keywords}})

    ####################   search term  #####################
    def list_search_term(self):
        ws = self.get_workspace_selected()

        if ws == None or "searchterm" not in ws or ws["searchterm"] == None:
            return []
        else:
            return list(ws["searchterm"])

    def save_search_term(self, search_terms):

        ws = self.get_workspace_selected()
        if ws == None:
            self.workspace_collection.upsert({"_id" : "_default"}, {'$set' : {"searchterm" : search_terms}})
        else:
            self.workspace_collection.update({"_id" : ObjectId(ws["_id"] )}, {'$set' : {"searchterm" : search_terms}})

    ############# HOST HELPERS ###########

    def get_hosts(self, show_all=None):
        if show_all:
            query = {}
        else:
            query = { "display": { "$ne": 0 } }

        sort_order = [("host_score", pymongo.DESCENDING),("_id", pymongo.ASCENDING)]
        docs = self.hostinfo_collection.find(query).sort(sort_order) # sort by _id to have deterministic results
        return docs

    def get_hosts_filtered(self, filter_field, filter_regex, show_all=None):
        if show_all:
            query = {'$and' : [{'$or':[{filter_field:{'$regex':filter_regex}},{"tags":{'$regex':filter_regex}}]}]}
        else:
            query = {'$and' : [{'$or':[{filter_field:{'$regex':filter_regex}},{"tags":{'$regex':filter_regex}}]}, { "display": { "$ne": 0 }}]}

        sort_order = [("host_score", pymongo.DESCENDING),("_id", pymongo.ASCENDING)] # sort by _id to have deterministic results
        docs = self.hostinfo_collection.find(query).sort(sort_order)
        return docs

    def get_hosts_by_tag_match(self, filter_regex, show_all=None):

        if show_all:
            query = {'$and' : [{"tags" : {'$regex' : filter_regex}}]}
        else:
            query = {'$and' : [{"tags" : {'$regex' : filter_regex}}, { "display": { "$ne": 0 }}]}

        sort_order = [("host_score", pymongo.DESCENDING),("_id", pymongo.ASCENDING)] # sort by _id to have deterministic results
        docs = self.hostinfo_collection.find(query).sort(sort_order)
        return docs

    def get_hosts_by_host_match(self, filter_regex, show_all=None):

        if show_all:
            query = {'$and' : [{"host" : {'$regex' : filter_regex}}]}
        else:
            query = {'$and' : [{"host" : {'$regex' : filter_regex}}, { "display": { "$ne": 0 }}]}

        sort_order = [("host_score", pymongo.DESCENDING),("_id", pymongo.ASCENDING)] # sort by _id to have deterministic results
        docs = self.hostinfo_collection.find(query).sort(sort_order)
        return docs

    ############# TAGS #############

    def save_tags(self, host, tags):
        self.hostinfo_collection.update({"host" : host}, {'$set' : {"tags" : tags}})

    def search_tags(self, term):
        #ws_doc  = self.hostinfo_collection.find({'$or':[{"host":{'$regex':term}},{"tags":{'$regex':term}}]}).sort("host_score", -1)
        #ws_doc  = self.get_hosts_filtered("host", term)
        tag_matches = self.get_hosts_by_tag_match(term)
        host_matches = self.get_hosts_by_host_match(term)
        ws_doc = {"tag_matches" : list(tag_matches), "host_matches" : list(host_matches)}

        if not tag_matches and not host_matches:
            return None
        else:
            return ws_doc

    def list_tags(self, host):
        ws_doc = self.hostinfo_collection.find_one({"host" : host})
        if None == ws_doc:
            return None
        else:
            return ws_doc['tags']

    ############# Display Hosts #############

    def save_display(self, host, displayable):
        self.hostinfo_collection.update({"host" : host}, {'$set': {'display': displayable}})
        self.urlinfo_collection.update({"host" : host}, {'$set': {'display': displayable}}, multi=True)


    ################ BLURRING #########################

    def get_blur_level(self):
        ws = self.get_workspace_selected()

        if ws == None or "blur_level" not in ws or ws["blur_level"] == None:
            return 0
        else:
            return ws["blur_level"]

    def save_blur_level(self, level):
        ws = self.get_workspace_selected()
        if ws == None:
            self.workspace_collection.upsert({"_id" : "_default"}, {'$set' : {"blur_level" : level}})
        else:
            self.workspace_collection.update({"_id" : ObjectId(ws["_id"] )}, {'$set' : {"blur_level" : level}})


if __name__ == "__main__":

    mmu = MemexMongoUtils()
    MemexMongoUtils(which_collection="crawl-data", init_db=True)
    MemexMongoUtils(which_collection="known-data", init_db=True)
    MemexMongoUtils(which_collection="cc-crawl-data", init_db=True)
    mmu.init_workspace()
#    mmu.insert_url(url = "http://www.google.com/")
#    print mmu.list_all_urls()
    
