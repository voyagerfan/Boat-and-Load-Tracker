from flask import Blueprint, request, jsonify, make_response
from google.cloud import datastore
import json
import constants
#import jwtcheck

from flask import _request_ctx_stack
from six.moves.urllib.request import urlopen
from flask_cors import cross_origin
from jose import jwt


import json
from os import environ as env
from werkzeug.exceptions import HTTPException

from dotenv import load_dotenv, find_dotenv
from flask import Flask
from flask import jsonify
from flask import redirect
from flask import render_template
from flask import session
from flask import url_for
from authlib.integrations.flask_client import OAuth
from six.moves.urllib.parse import urlencode, quote_plus


client = datastore.Client()

bp = Blueprint('boats', __name__, url_prefix='/boats')

CLIENT_ID = 'Enter Auth0 client ID from App here'
CLIENT_SECRET = 'Enter Auth0 client client from App here'
DOMAIN = 'enter domain from Auth0 here'
ALGORITHMS = ["RS256"]

# This code is adapted from https://auth0.com/docs/quickstart/backend/python/01-authorization?_ga=2.46956069.349333901.1589042886-466012638.1589042885#create-the-jwt-validation-decorator

class AuthError(Exception):
    def __init__(self, error, status_code):
        self.error = error
        self.status_code = status_code


@bp.errorhandler(AuthError)
def handle_auth_error(ex):
    response = jsonify(ex.error)
    response.status_code = ex.status_code
    return response

# Verify the JWT in the request's Authorization header
def verify_jwt(request):
    if 'Authorization' in request.headers:
        auth_header = request.headers['Authorization'].split()
        token = auth_header[1]
    else:
        raise AuthError({"code": "no auth header",
                            "description":
                                "Authorization header is missing"}, 401)
    
    jsonurl = urlopen("https://"+ DOMAIN+"/.well-known/jwks.json")
    jwks = json.loads(jsonurl.read())
    try:
        unverified_header = jwt.get_unverified_header(token)
    except jwt.JWTError:
        raise AuthError({"code": "invalid_header",
                        "description":
                            "Invalid header. "
                            "Use an RS256 signed JWT Access Token"}, 401)
    if unverified_header["alg"] == "HS256":
        raise AuthError({"code": "invalid_header",
                        "description":
                            "Invalid header. "
                            "Use an RS256 signed JWT Access Token"}, 401)
    rsa_key = {}
    for key in jwks["keys"]:
        if key["kid"] == unverified_header["kid"]:
            rsa_key = {
                "kty": key["kty"],
                "kid": key["kid"],
                "use": key["use"],
                "n": key["n"],
                "e": key["e"]
            }
    if rsa_key:
        try:
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=ALGORITHMS,
                audience=CLIENT_ID,
                issuer="https://"+ DOMAIN+"/"
            )
        except jwt.ExpiredSignatureError:
            raise AuthError({"code": "token_expired",
                            "description": "token is expired"}, 401)
        except jwt.JWTClaimsError:
            raise AuthError({"code": "invalid_claims",
                            "description":
                                "incorrect claims,"
                                " please check the audience and issuer"}, 401)
        except Exception:
            raise AuthError({"code": "invalid_header",
                            "description":
                                "Unable to parse authentication"
                                " token."}, 401)

        return payload
    else:
        raise AuthError({"code": "no_rsa_key",
                            "description":
                                "No RSA key in JWKS"}, 401)

@bp.route('', methods=['POST','GET'])
def boats_get_post():
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

    #verify the jwt. 
    payload = verify_jwt(request)
    
    if request.method == 'POST':
     
        newOwner = payload['sub']
        content = request.get_json()
        validContent = 0
        load = [] #loads array
        for element in content:
            if element == 'name' or element =='type' or element == 'length':
                validContent += 1
        if validContent == 3:
            new_boat = datastore.entity.Entity(key=client.key(constants.boats))
            new_boat.update({'owner': newOwner, 'name': content['name'], 'type': content['type'], 'length': content['length'], "loads": load, 'id': None, "self": None})
            client.put(new_boat)
            new_boat.update({"id": new_boat.key.id, "self": constants.host + bp.url_prefix + "/" + str(new_boat.key.id)})
            client.put(new_boat)
            return (jsonify(new_boat), 201)
        else:
            error = {"Error": "The request object is missing at least one of the required attributes"}
            return(jsonify(error), 400)

    elif request.method == 'GET':
        #get the boat owner     
        boatOwner = payload["sub"]

        #query the datastore for count of items by owner
        queryTotal = client.query(kind=constants.boats)
        queryTotal.add_filter("owner", "=", str(boatOwner))
        resultsTotal = list(queryTotal.fetch())
        #if the user exists respond with the note dont do anything
        totalCount = 0
        for element in resultsTotal:
            totalCount +=1

        #query the datastore filtering for the boat owner, implement pagination
        query = client.query(kind=constants.boats)
        query.add_filter("owner", "=", str(boatOwner))
        #paginate w/ 5 entities at a time
        q_limit = int(request.args.get('limit', '5'))
        q_offset = int(request.args.get('offset', '0'))
        l_iterator = query.fetch(limit= q_limit, offset=q_offset)
        pages = l_iterator.pages
        results = list(next(pages))
        if l_iterator.next_page_token:
            next_offset = q_offset + q_limit
            next_url = request.base_url + "?limit=" + str(q_limit) + "&offset=" + str(next_offset)
        else:
            next_url = None
        for e in results:
            e["id"] = e.key.id
        output = {"boats": results}
        output["Total Results"] = totalCount
        if next_url:
            output["next"] = next_url
        return (jsonify(output), 200)
    else:
        return ('Method not recogonized', 405)

@bp.route('/<id>', methods=['DELETE', 'GET', 'PATCH', 'PUT']) 
def boats_put_delete_get(id):
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

    #control for the id
    boat_key = client.key(constants.boats, int(id))
    boat = client.get(key=boat_key)
    if boat is None:
        error = {"Error": "No boat with this boat_id exists"}
        return (jsonify(error), 404)

    #verify the jwt. 
    
    payload = verify_jwt(request)
    
    #verify if jwt 'sub' == the boat owner
    jwtID = payload['sub']
    boatOwner = boat['owner']
    if boatOwner != jwtID:
        error = {"Error": "Requester is not the same as the boat owner"}
        return((jsonify(error)), 403)
    
    
    if request.method == 'DELETE':
        #find the load (if available) and update the carrier attribute to None
        for element in boat['loads']:
            if 'id' in element.keys():
                load_key = client.key(constants.loads, int(element['id']))
                load = client.get(key=load_key)
                load.update({"carrier": None})
                client.put(load)
                    
        #delete the boat
        client.delete(boat_key)
        return ('',204)
        
        
    elif request.method == "GET":
        #return the boat entity
        return (jsonify(boat), 200)
    
    elif request.method == 'PUT':
        #get the request content 
        content = request.get_json()
        attributeCounter = 0
        
        #count the response body to ensure it has all 3 attributes.
        for element in content:
            if element == 'name' or element =='type' or element == 'length':
                attributeCounter += 1
        if attributeCounter < 3:
            error = {"Error":"Incorrect number of attributes or types"}
            return (jsonify(error), 400)
        else:
            #update the boat
            boat.update({'name': content['name'], 'type': content['type'], 'length': content['length']})
            client.put(boat)
            return(jsonify(boat), 204)

    elif request.method == 'PATCH':
        #declare blank array and get the json content
        elementArr = []
        content = request.get_json()

        #append relevant attributes to an array
        elementCounter = 0
        for element in content:
            if element == 'name' or element =='type' or element == 'length':
                elementCounter += 1
                elementArr.append(element)
        
        #control for the number of elements
        if elementCounter == 0 or elementCounter > 3:
            error = {"Error": "Incorrect number of attributes or types"}
            return (jsonify(error), 400)

        #loop through array update relevant attributes to the load.
        for i in range(0, len(elementArr)):
            boat.update({elementArr[i]:content[elementArr[i]]})
            client.put(boat)

        #create the response
        res = make_response(json.dumps(boat))
        res.mimetype = 'application/json'
        res.content_type = 'application/json'
        res.status_code = 204
        return res
    else:
        return ('Method not recogonized', 405)

@bp.route('/<bid>/loads/<lid>', methods=['PUT','DELETE'])
def add_delete_boatload(bid,lid):
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

    #control for the id
    load_key = client.key(constants.loads, int(lid))
    load = client.get(key=load_key)
    boat_key = client.key(constants.boats, int(bid))
    boat = client.get(key=boat_key)
    if boat is None or load is None:
        error = {"Error": "The specified boat and/or load does not exist"}
        return (jsonify(error), 404)

    #verify the jwt. 
    
    payload = verify_jwt(request)

    #verify if jwt 'sub' == the boat owner
    jwtID = payload['sub']
    boatOwner = boat['owner']
    if boatOwner != jwtID:
        error = {"Error": "Requester is not the same as the boat owner"}
        return((jsonify(error)), 403)

    if request.method == 'PUT':
        #loop through the id's on the boat.
        #if found, error out since the load is already there.
        for element in boat['loads']:
            if 'id' in element.keys():
                if element['id'] == int(lid):
                    error = {"Error":"The load is already loaded on a boat"}
                    return(jsonify(error), 403)

        #add the load to th boat. Update the carrier attribute of the load.  
        boat['loads'].append({"id":load['id'], "item":load['item'], "creation_date":load['creation_date'], "volume":load['volume'], "self":load['self']})
        load['carrier'] = {'id':boat['id'], 'self':boat['self']}
        client.put(boat)
        client.put(load) 
        return(jsonify(boat),204)

    elif request.method == 'DELETE':
        loadFound = False
        #loop through the loads and remove the load from the boat if found
        for element in boat['loads']:
            if 'id' in element.keys():
                if element['id'] == int(lid):
                    loadFound = True
                    boat['loads'].remove(element)
                    client.put(boat)
                    
        #update the carrier attribute of the load if it was found
        if loadFound == True:
            load.update({"carrier": None})
            client.put(load)
            return('', 204)
        else:
            error = {"Error":"No boat with this boat_id is loaded with the load with this load_id"}
            return(jsonify(error), 404)
    else:
        return ('Method not recogonized', 405)

@bp.route('/<id>/loads', methods=['GET'])
def get_allLoads_forboat(id):
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

    if request.method == 'GET':
        boat_key = client.key(constants.boats, int(id))
        boat = client.get(key=boat_key)
        if boat is not None:
            load_list = []
            if 'loads' in boat.keys():
                for element in boat['loads']:
                    if 'id' in element.keys():
                        load_key = client.key(constants.loads, int(element['id']))
                        load_list.append(load_key)
                        final_list = {"loads":client.get_multi(load_list)}
                return (jsonify(final_list), 200)
            else:
                return json.dumps([])
        else:
            error = {"Error":"No boat with this boat_id exists"}
            return(jsonify(error), 404)
    else:
        return ('Method not recogonized', 405)
        
    
