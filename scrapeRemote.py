#imports:
import pandas as pd
import numpy as np
import requests
import json
import tensorflow_hub as hub
import re
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
stop_words = set(stopwords.words('english'))
from bs4 import BeautifulSoup
from requests import utils
from tqdm import tqdm
import argparse
import time
from time import strftime, localtime
import datetime


embed = hub.load("https://tfhub.dev/google/universal-sentence-encoder/4")


#get wikipedia url from a wikidata id
def get_wikipedia_url_from_wikidata_id(wikidata_id, lang='en', debug=False):
    """code from: https://stackoverflow.com/questions/37079989/how-to-get-wikipedia-page-from-wikidata-id"""

    url = (
        'https://www.wikidata.org/w/api.php'
        '?action=wbgetentities'
        '&props=sitelinks/urls'
        f'&ids={wikidata_id}'
        '&format=json')
    json_response = requests.get(url).json()
    if debug: print(wikidata_id, url, json_response) 

    entities = json_response.get('entities')    
    if entities:
        entity = entities.get(wikidata_id)
        if entity:
            sitelinks = entity.get('sitelinks')
            if sitelinks:
                if lang:
                    # filter only the specified language
                    sitelink = sitelinks.get(f'{lang}wiki')
                    if sitelink:
                        wiki_url = sitelink.get('url')
                        if wiki_url:
                            return requests.utils.unquote(wiki_url)
                else:
                    # return all of the urls
                    wiki_urls = {}
                    for key, sitelink in sitelinks.items():
                        wiki_url = sitelink.get('url')
                        if wiki_url:
                            wiki_urls[key] = requests.utils.unquote(wiki_url)
                    return wiki_urls
    return None   




#preprocess data:
def preProcessData(data : list, numberOfElements):
    """takes in the data from sparQL, and converts it to just a list of ids. Returs array of length numberOfElements"""
    ids = []
    for idx, ele in enumerate(data):
        if (idx >= numberOfElements):
            return ids
        url = ele[0]
        urlArr = url.split("/")
        wikidataId = urlArr[-1]
        ids.append(wikidataId)
    return ids

def getIsbnFromBookTitle(bookTitle : str):
    """uses google book api, assumes first suggestion is the book you are looking for"""
    response = requests.get(f"https://www.googleapis.com/books/v1/volumes?q=intitle:{bookTitle}").json()
    bookResponse = (response.get("totalItems", ""))
    if (bookResponse == "" or bookResponse == 0):
        return None
    responseArr = response["items"]
    isbn = responseArr[0]
    try: 
        return isbn.get("volumeInfo", "").get("industryIdentifiers")[0].get("identifier")
    except:
        print("Could not get book isbn from title")
        return None



def getSoup(url):
    response = requests.get(url=url)
    soup = BeautifulSoup(response.content, 'html.parser')
    return soup

def getTitleAndSummaryFromWikipediaPage(soup):
    title = soup.select("#firstHeading")[0].text
    headers = soup.find_all(['h1', 'h2', 'h3'])

    relevantHeader = None
    for i in range(len(headers)):
        firstString = re.split('[^a-zA-Z]', headers[i].getText())[0]
        if (firstString.lower() == "plot" or firstString.lower() == "summary"):
            relevantHeader = (headers[i])
    if (relevantHeader == None):
        return None
    summary = ""
    for elem in relevantHeader.next_siblings:
        if elem.name and elem.name.startswith('h'):
            # stop at next header
            break
        if elem.name == 'p':
            summary += (elem.get_text())+" "
            #f.write(elem.get_text() + u'\n')
    return title, summary

def removeStopWords(string) -> str:
    """takes in a string, removes stop words from it, and returns the string without stopwords"""
    word_tokens = word_tokenize(string)
    filtered_sentence = [w for w in word_tokens if not w.lower() in stop_words]
    return " ".join(filtered_sentence)

def getAllLinksFromPage(soup):
    allLinks = soup.find(id="bodyContent").find_all("a")
    res = []
    for ele in allLinks:
        if (ele.has_attr("href") and ele['href'].find("/wiki/") != -1):
            res.append(ele)
    return res


def scrape(listOfIdsToScrape, numberOfElementsToScrape : int, filename, maxTimeInSeconds):
    titleAndEncodedSummaries = dict()
    numberOfSummariesAdded = 0

    startTime = time.time()
    endTime = startTime + maxTimeInSeconds

    for idx, idToScrape in tqdm(enumerate(listOfIdsToScrape)):
        if (numberOfSummariesAdded >= numberOfElementsToScrape or time.time() >= endTime):
            break
        try:
            wikipediaUrl = get_wikipedia_url_from_wikidata_id(idToScrape) #
            soup = getSoup(wikipediaUrl)
            res = getTitleAndSummaryFromWikipediaPage(soup)
            if (res is None):
                continue
            title, summary = res

            numberOfSummariesAdded += 1
            nonStopWordSummary = removeStopWords(summary)
            embedding = embed([nonStopWordSummary]).numpy().tolist() #make embedding, convert it to np array
            isbn = getIsbnFromBookTitle(title)
            if (isbn):
                embedding.insert(0, isbn) #store isbn if we can find it
            else:
                embedding.insert(0, "")
            titleAndEncodedSummaries[title] = embedding
        except:
            pass

    #end by writing the data to file
    with open(filename, "w") as f:
        json.dump(titleAndEncodedSummaries, f)
    f.close()
    print(f"Added {numberOfSummariesAdded} books")
    

if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    #-db DATABSE -u USERNAME -p PASSWORD -size 20
    parser.add_argument("-numids", "--ids", help="Number of id's to scrape from")
    parser.add_argument("-numbooks", "--books", help="Number of books to scrape")
    parser.add_argument("-maxtime", "--time", help="Maximum number of seconds to scrape")

    args = parser.parse_args()
    numberOfIdsToGet = 0
    numberOfBooksToScrape = 0
    maxNumberOfSecondsToScrape = 0
    print(f"Getting {args.ids} wikidata ids, and scraping {args.books} books...")
    if (args.ids and args.books and args.time):
        numberOfIdsToGet = int(args.ids)
        numberOfBooksToScrape = int(args.books)
        maxNumberOfSecondsToScrape = int(args.time)
    else:
        print("Exiting. You have to set number of ids to get with the: -numids flag, and number of books to scrape with the -numbooks flag")
        exit()

        
    allIds = pd.read_csv("wikidataLitteratureWorkIds.csv")
    allIdsNp = allIds.to_numpy()
    print("Preprocessing...")
    ids = preProcessData(allIdsNp, numberOfIdsToGet)
    print("Scraping...")
    scrape(ids, numberOfBooksToScrape, "bookTitleAndSummaries.json", maxNumberOfSecondsToScrape)
    print("Done")


