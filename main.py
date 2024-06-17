from google.cloud import datastore
from flask import Flask, request, jsonify, _request_ctx_stack

import requests


from functools import wraps
import json

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

import boats
import loads
import owner
import jwtcheck
import constants

app = Flask(__name__)
app.register_blueprint(boats.bp)
app.register_blueprint(loads.bp)
app.register_blueprint(owner.bp)
app.register_blueprint(jwtcheck.bp)

app.secret_key = 'SECRET_KEY'

client = datastore.Client()



# Update the values of the following 3 variables
CLIENT_ID = 'Enter Auth0 client ID from App here'
CLIENT_SECRET = 'Enter Auth0 client client from App here'
DOMAIN = 'enter domain from Auth0 here'
# For example
# DOMAIN = 'fall21.us.auth0.com'

ALGORITHMS = ["RS256"]

ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)

oauth = OAuth(app)

auth0 = oauth.register(
    'auth0',
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    api_base_url="https://" + DOMAIN,
    access_token_url="https://" + DOMAIN + "/oauth/token",
    authorize_url="https://" + DOMAIN + "/authorize",
    client_kwargs={
        'scope': 'openid profile email',
    },
    server_metadata_url=f'https://dev-llzmw6w3z0rv13sm.us.auth0.com/.well-known/openid-configuration'
)

# This code is adapted from https://auth0.com/docs/quickstart/backend/python/01-authorization?_ga=2.46956069.349333901.1589042886-466012638.1589042885#create-the-jwt-validation-decorator

class AuthError(Exception):
    def __init__(self, error, status_code):
        self.error = error
        self.status_code = status_code


@app.errorhandler(AuthError)
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


@app.route('/')
def index():
    return render_template('home2.html')

# Create a lodging if the Authorization header contains a valid JWT
@app.route('/boats', methods=['POST', 'GET'])
def get_and_post_boats():
    if request.method == 'POST':
         #set an owner variable
        boatOwner = ""

        #verify the jwt. payload is the decoded version
        try:
            payload = verify_jwt(request)
        except:
            return ('', 401)

        #turn the payload into json
        #payload = payload.json()

        #find the owner
        boatOwner = payload["sub"]
        print(boatOwner)
        
        content = request.get_json()
        new_boat = datastore.entity.Entity(key=client.key(constants.BOATS1))
        new_boat.update({"name": content["name"], "type": content["type"],
          "length": content["length"], "public": content["public"], "owner": boatOwner})
        client.put(new_boat)
        new_boat.update({"id": new_boat.key.id})
        client.put(new_boat)
        return (jsonify(new_boat), 201)

    elif request.method == 'GET':
        
        returnArr =[]
        try:
            payload = verify_jwt(request)
        except:
            #if jwt error, list all public boats regardless of owner 
            returnArr =[]
            query = client.query(kind=constants.BOATS1)
            query.add_filter("public", "=", "true")
            results = list(query.fetch())
            for e in results:
                e["id"] = e.key.id
            for element in results:
                formatedData = jsonify(element)
                returnArr.append(element)
            return returnArr, 200

        #if the jwt is valid, return the public boats for the owner.
        
        #find the owner
        boatOwner = payload["sub"]
        
        #run a query for the owner and the public = true
        query = client.query(kind=constants.BOATS1)
        query.add_filter("owner", "=", str(boatOwner))
        query.add_filter("public", "=", "true")
        results = query.fetch()
        results = list(results)
        
        return (results, 200)
        
    else:
        return jsonify(error='Method not recogonized')

@app.route('/owners/<owner_id>/boats', methods=['GET'])
def get_owner_boats(owner_id):
    if request.method == 'GET':
        returnArr =[]
        try:
            payload = verify_jwt(request)
        except:
            query = client.query(kind=constants.BOATS1)
            query.add_filter("owner", "=", str(owner_id))
            query.add_filter("public", "=", "true")
            results = query.fetch()
            results = list(results)
           
            return (results, 200)
        
        #if no jwt exceptions, run the query anyway
        query = client.query(kind=constants.BOATS1)
        query.add_filter("owner", "=", str(owner_id))
        query.add_filter("public", "=", "true")
        results = query.fetch()
        results = list(results)
        
        return (results, 200)
    else:
        return jsonify(error='Method not recogonized')

@app.route('/boats/<boat_id>', methods=['DELETE'])
def delete_boat_by_id(boat_id):
    if request.method == 'DELETE':
        try:
            payload = verify_jwt(request)
        except:
            return('', 401)
        
        #find the boat with the <boat_id>
        boat_key = client.key(constants.BOATS1, int(boat_id))
        boat = client.get(key=boat_key)
        if boat is None:
            return ('', 403)

        #get the boat owner of the boat associated with <boat_id>
        boatOwner = boat['owner']

        #get the detele requester (sub value in jwt)
        requester = payload["sub"]
       
        if requester == boatOwner:
            client.delete(boat_key)
            return('',204)
        elif boat is None or requester != boatOwner:
            mismatch = {
                "error" : "owner does not match requestor. Cannot Delete",
                "requester": requester,
                "owner": boatOwner
                }
            return (jsonify(mismatch),403)
    else:
        return jsonify(error='Method not recogonized')

# Decode the JWT supplied in the Authorization header
@app.route('/decode', methods=['GET'])
def decode_jwt():
    payload = verify_jwt(request)
    return payload          
        

# Generate a JWT from the Auth0 domain and return it
# Request: JSON body with 2 properties with "username" and "password"
#       of a user registered with this Auth0 domain
# Response: JSON with the JWT as the value of the property id_token
@app.route("/login")
def login():
    return oauth.auth0.authorize_redirect(
        redirect_uri=url_for("callback", _external=True)
    )

@app.route("/callback", methods=["GET", "POST"])
def callback():
    token = oauth.auth0.authorize_access_token()
    session["user"] = token
    
    userJWT = ""
    for element in token:
        if element == 'id_token':
            userJWT = token[element]
    
    url2 = constants.host + '/decode'
    headers2 = {
        'content-type': 'application/json', 
        "Authorization": "Bearer " + userJWT}
    
    user = ""
    email = ""
    name = ""

    #send get request to decode the JWT
    payload = requests.get(url2, headers=headers2)
    payload = payload.json()

    #gather the attributes
    for key in payload:
        if key == 'sub':
            user = payload[key]
        if key == 'email':
            email = payload[key]
        if key == 'name':
            name = payload[key]
    
    #prep post request 
    url3 = constants.host + '/owner'
    headers3 = {
        'content-type': 'application/json'
    }
    body = {
        "authoID":user,
        "name":name,
        "email":email
    }
    
    #send post request to /owner handler to add the user
    ownerResponse = requests.post(url3, json=body)
    
    
    #use one of the 2 below when ready for rendering on the template
    resCode = ownerResponse.status_code
    if resCode == 204:
        created = "Owner entity already exists in the data Store. New entity not created"
    elif resCode == 201:
        created = "New owner entity has been created for you"
    else:
        created = "Issue with creating a new owner entity"
    
    return render_template('home2.html', encodedJWT=userJWT, decodedData=payload, userID=user, entityStatus=created)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(
        "https://" + DOMAIN
        + "/v2/logout?"
        + urlencode(
            {
                "returnTo": url_for("index", _external=True),
                "client_id": CLIENT_ID,
            },
            quote_via=quote_plus,
        )
    )

    
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)