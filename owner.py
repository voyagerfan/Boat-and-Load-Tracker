from flask import Blueprint, request, jsonify
from google.cloud import datastore
import json
import constants
import jwtcheck

client = datastore.Client()

bp = Blueprint('owner', __name__, url_prefix='/owner')

@bp.route('', methods=['POST','GET'])
def owner_get_post():
    #check accept header for application/json or */*
    foundJson = False
    if 'Accept' in request.headers:
        accept_header = request.headers['Accept'].split()
        for element in accept_header:
            if element == 'application/json' or element == '*/*':
                foundJson = True
                break
        if foundJson == False:
            error = {"Error": "Accept header from requester does not support JSON"}
            return(jsonify(error), 406)
            
    if request.method == 'POST':
        content = request.get_json()
        validContent = 0
        load = [] #loads array
        #count the content 
        for element in content:
            if element == 'name' or element =='email' or element == 'authoID':
                validContent += 1
        if validContent < 3:
            error: {"Error":"Request body does not contain all valid elements"}
            return(jsonify(erorr), 400)
        #query the datastore to see if the authoID already exists
        query = client.query(kind=constants.owner)
        query.add_filter("authoID", "=", str(content['authoID']))
        results = list(query.fetch())
        #if the user exists respond with the note dont do anything
        counter = 0
        for result in results:
            counter +=1
        if counter > 0:
            note = {"Note":"Entity wth AuthoId already exists in the datastore. New user id NOT created"}
            return (jsonify(note),204)
        
        #else, create the entity.
        else:
            new_owner = datastore.entity.Entity(key=client.key(constants.owner))
            new_owner.update({'name': content['name'], 'email': content['email'], 'authoID': content['authoID']})
            client.put(new_owner)
            new_owner.update({"id": new_owner.key.id, "self": constants.host + bp.url_prefix + "/" + str(new_owner.key.id)})
            client.put(new_owner)
            note = {"Note": "New user created in the datastore"}
            return (jsonify(note), 201)

    elif request.method == 'GET':
        query = client.query(kind=constants.owner)
        results = list(query.fetch())
        return (jsonify(results), 200)
    else:
        return ('Method not recogonized', 405)