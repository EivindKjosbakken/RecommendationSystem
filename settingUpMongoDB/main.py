from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_cors import CORS, cross_origin
import functools
import json

import requests
import pymongo
import random

mongo_client = pymongo.MongoClient("mongodb://127.0.0.1:27017/?directConnection=true&serverSelectionTimeoutMS=2000&appName=mongosh+1.7.1") 

app = Flask(__name__)

cors = CORS(app)

APP_URL = "/"


database = mongo_client["testDB"]
testTable = database["testTable"]



@app.route(f"{APP_URL}/testPost", methods=["POST"]) 
def testPostApi():
    data = request.json
    #print("DATA IS: ", data)
    bookName = data["bookName"]
    isTest = True
    
    if isTest:
        randomInteger = random.randint(1, 10000)
        testTable.insert_one({"index": randomInteger, "book": bookName})
        return "Called test endpoint", 200
    return "Test api method failed", 400


@app.route(f"{APP_URL}/testGet", methods=["GET"]) 
def testGetApi():
    print("get test endpoint is called")

    isTest = True
    
    if isTest:
        res = testTable.find_one({"book": "Eivinds bok"})["index"]
        print(res)

        return {"res1": res}, 200
        #return {"test": json.dumps(res)}
    return "Test api method failed", 400