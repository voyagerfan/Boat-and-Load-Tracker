from flask import Blueprint, request, jsonify, make_response
from google.cloud import datastore
import json
import constants


client = datastore.Client()

bp = Blueprint('loads', __name__, url_prefix='/loads')

@bp.route('', methods=['POST','GET'])
def loads_get_post():
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
        for element in content:
            if element == 'volume' or element =='item' or element == 'creation_date':
                validContent += 1
        if validContent == 3:
            new_load = datastore.entity.Entity(key=client.key(constants.loads))
            new_load.update({'volume': content['volume'], 'item': content['item'], 'creation_date': content['creation_date'], 'id': None, "self": None, "carrier": None})
            client.put(new_load)
            new_load.update({"id": new_load.key.id, "self": constants.host + bp.url_prefix + "/" + str(new_load.key.id)})
            client.put(new_load)
            return (jsonify(new_load), 201)
        else:
            error = {"Error": "The request object is missing at least one of the required attributes"}
            return(jsonify(error), 400)
            
    elif request.method == 'GET':
        queryTotal = client.query(kind=constants.loads)
        results = list(queryTotal.fetch())
        #if the user exists respond with the note dont do anything
        elementCounter = 0
        for element in results:
            elementCounter +=1

        #query the data store for loads and implement pagination
        query = client.query(kind=constants.loads)
        q_limit = int(request.args.get('limit', '5'))
        q_offset = int(request.args.get('offset', '0'))
        g_iterator = query.fetch(limit= q_limit, offset=q_offset)
        pages = g_iterator.pages
        results = list(next(pages))
        if g_iterator.next_page_token:
            next_offset = q_offset + q_limit
            next_url = request.base_url + "?limit=" + str(q_limit) + "&offset=" + str(next_offset)
        else:
            next_url = None
        for e in results:
            e["id"] = e.key.id
        output = {"loads": results}
        output["Total Results"] = elementCounter
        if next_url:
            output["next"] = next_url
        return (jsonify(output), 200)


@bp.route('/<id>', methods=['PUT','DELETE', 'GET', 'PATCH']) 
def load_put_delete(id):
    #get the load entity by ID
    load_key = client.key(constants.loads, int(id))
    load = client.get(key=load_key)

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

    #if load is NULL, the ID is not correct
    if load is None:
        error = {"Error": "No load with this load_id exists"}
        return (jsonify(error), 404)

            
    if request.method == 'DELETE':
        
        # Check to see if the load has a carrier
        if load['carrier'] is not None:

            #get the boat
            carrier_id = load['carrier']['id']
            boat_key = client.key(constants.boats, int(carrier_id))
            boat = client.get(key=boat_key)

            #loop through the loads on the boat and remove the load,
            # from the boat if it exists
            for element in boat['loads']:
                if 'id' in element.keys():
                    if element['id'] == int(id):
                        boat['loads'].remove(element)
                        client.put(boat)

        # Delete the load
        client.delete(load_key)
        return ('',204)

    elif request.method == 'GET':
        
        return (jsonify(load), 200)

    elif request.method == 'PUT':
        #get the request content 
        content = request.get_json()
        attributeCounter = 0
        
        #count the response body to ensure it has all 3 attributes.
        for element in content:
            if element == 'volume' or element =='item' or element == 'creation_date':
                attributeCounter += 1
        if attributeCounter < 3:
            error = {"Error":"Incorrect number of valid attributes"}
            return (jsonify(error), 400)
        else:
            #update the load
            load.update({'volume': content['volume'], 'item': content['item'], 'creation_date': content['creation_date']})
            client.put(load)

            #update the boat that has this load
            if load['carrier'] is not None:
                carrier_id = load['carrier']['id']
                boat_key = client.key(constants.boats, int(carrier_id))
                boat = client.get(key=boat_key)

                #loop through the loads on a boat and remove it
                for element in boat['loads']:
                    if 'id' in element.keys():
                        if element['id'] == int(id):
                            boat['loads'].remove(element)
                            client.put(boat)
                
                #append the modified load to the "loads" attribute
                load_key = client.key(constants.loads, int(id))
                load = client.get(key=load_key)
                boat['loads'].append({"id":load['id'], "item":load['item'], "creation_date":load['creation_date'], "volume":load['volume'], "self":load['self']})
                client.put(boat)

            return(json.dumps(load), 204)

    elif request.method == 'PATCH':
        elementArr = []
        content = request.get_json()

        #append relevant attributes to a an array
        elementCounter = 0
        for element in content:
            if element == 'volume' or element =='item' or element == 'creation_date':
                elementCounter += 1
                elementArr.append(element)
        print("the number of elements is")
        print(elementCounter)
        #control for the number of elements
        if elementCounter == 0 or elementCounter > 3:
            error = {"Error": "Incorrect number of valid attributes"}
            
            return (jsonify(error), 400)

        #loop through array update relevant attributes to the load.
        for i in range(0, len(elementArr)):
            load.update({elementArr[i]:content[elementArr[i]]})
            client.put(load)

        #update the boat if has this load
        if load['carrier'] is not None:
            carrier_id = load['carrier']['id']
            boat_key = client.key(constants.boats, int(carrier_id))
            boat = client.get(key=boat_key)

            #loop through the loads on a boat and remove it
            for element in boat['loads']:
                if 'id' in element.keys():
                    if element['id'] == int(id):
                        boat['loads'].remove(element)
                        client.put(boat)
                        break
                
            #append the modified load
            load_key = client.key(constants.loads, int(id))
            load = client.get(key=load_key)
            boat['loads'].append({"id":load['id'], "item":load['item'], "creation_date":load['creation_date'], "volume":load['volume'], "self":load['self']})
            client.put(boat)

        #create the response
        res = make_response(json.dumps(load))
        res.mimetype = '*/*'
        res.content_type = '*/*'
        res.status_code = 200
        return res

    else:
        return 'Method not recogonized'