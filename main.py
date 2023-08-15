from flask import Flask, request, Response, make_response, jsonify
import psycopg2
from flask_cors import CORS, cross_origin
import uuid
import json
import threading
import time
import datetime
from flask.json import JSONEncoder



"""
POSTGRES SQL TABLES:
users (
      id VARCHAR(40),
      token VARCHAR(40),
      name VARCHAR(100),
      admin boolean,
      password VARCHAR(100),
      signups hstore,
      attended hstore,
      email VARCHAR(100),
      points integer,
      hours integer,
      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
   )


events (
      id VARCHAR(40),
      name VARCHAR(100),
      points integer,
      hours integer,
      signups hstore,
      attended hstore,
      code VARCHAR(6),
      datetime TIMESTAMP,
      finished boolean,
      address VARCHAR(256),
      description TEXT,
      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
   )
"""


class CustomJSONEncoder(JSONEncoder):
    def default(self, obj):
        try:
            if isinstance(obj, datetime.datetime) or isinstance(obj, datetime.date):
                return obj.isoformat()
            iterable = iter(obj)
        except TypeError:
            pass
        else:
            return list(iterable)
        return JSONEncoder.default(self, obj)


app = Flask(__name__)
app.secret_key = "h4hofficers_2023-2024"
CORS(app, support_credentials=True)
sqlconnection=psycopg2.connect("postgres://jyfevcqkwalgqs:c2870006a828b731edcec7dfe857eef0c1a16a04574663fd6426b99acae40474@ec2-54-205-67-130.compute-1.amazonaws.com:5432/d3u6qm55fhhdoa")
officeremails=["nichuhegde@gmail.com"]
app.json_encoder = CustomJSONEncoder

def _build_cors_preflight_response():
    response = make_response()
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add('Access-Control-Allow-Headers', "*")
    response.headers.add('Access-Control-Allow-Methods', "*")
    return response

def execute_query(query, params):
    try:
        cursor = sqlconnection.cursor()
        cursor.execute(query, params)
        result = cursor.fetchall()
        sqlconnection.commit()
        cursor.close()
    except Exception as e:
        print(str(e))
        sqlconnection.rollback()
    return result

def execute_commit_query(query, params):
    try:
        cursor = sqlconnection.cursor()
        cursor.execute(query, params)
        sqlconnection.commit()
        cursor.close()
    except Exception as e:
        print(str(e))
        sqlconnection.rollback()

def checkifloggedin(token):
    tokens = execute_query("SELECT id FROM users WHERE token=%s;", (token,))
    if len(tokens)>0:
        return True
    return False

def checkifadmin(token):
    if checkifloggedin(token):
        admin=bool(execute_query("SELECT admin FROM users WHERE token=%s;", (token,))[0])
        return admin
    return False

def getuserdata(token):
    cursor = sqlconnection.cursor()
    cursor.execute("SELECT * FROM users WHERE token=%s;", (token,))
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in rows]

def getallevents():
    cursor = sqlconnection.cursor()
    cursor.execute("SELECT * FROM events")
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in rows]

@app.route('/')
@cross_origin(support_credentials=True)
def serve():
    return 0
#send_from_directory(app.static_folder, 'index.html')

@app.route('/api/login', methods=["POST", "OPTIONS"])
@cross_origin(support_credentials=True)
def login():
    if request.method == "OPTIONS":
        return _build_cors_preflight_response()
    token=request.get_json()["token"]
    if checkifloggedin(token):
        return Response(json.dumps({"message" : "user already logged in!"}), status=403)
    email = request.get_json()["email"]
    password = request.get_json()["password"]
    emails = execute_query("SELECT email FROM users WHERE email=%s AND password=%s;", (email, password))
    if len(emails)>0:
        token = str(uuid.uuid4())
        execute_commit_query("UPDATE users SET token=%s WHERE email=%s AND password=%s;", (token, email, password))
        response=Response(json.dumps({"message" : "Logged in!", "token" : token}), status=200)
    else:
        response=Response(json.dumps({"message" : "User does not exist!"}), status=401)
    return response

@app.route('/api/logout', methods=["POST", "OPTIONS"])
@cross_origin(support_credentials=True)
def logout():
    if request.method == "OPTIONS":
        return _build_cors_preflight_response()
    token=request.get_json()["token"]
    if not checkifloggedin(token):
        return Response(json.dumps({"message" : "No user logged in!"}), status=403)
    execute_commit_query("UPDATE users SET token=%s WHERE token=%s;", ('', token))
    return Response(json.dumps({"authenticated" : False}), status=200)

@app.route('/api/signup', methods=["POST", "OPTIONS"])
@cross_origin(support_credentials=True)
def signup():
    if request.method == "OPTIONS":
        return _build_cors_preflight_response()
    token=request.get_json()["token"]
    if checkifloggedin(token):
        return Response(json.dumps({"message" : "User already logged in!"}), status=403)
    email = request.get_json()["email"]
    name = request.get_json()["name"]
    password = request.get_json()["password"]
    emails = execute_query("SELECT email FROM users WHERE email=%s;", (email,))
    names = execute_query("SELECT name FROM users WHERE name=%s;", (name,))
    admin=True if email in officeremails else False
    id = str(uuid.uuid4())
    if len(emails)==0 and len(names)==0:
        execute_commit_query("INSERT INTO users(name, password, email, token, admin, points, hours, id, signups, attended) VALUES (%s, %s, %s, '', %s, 0, 0, %s, ''::hstore, ''::hstore);", (name, password, email, admin, id))
        response=Response(json.dumps({"message" : "Account made!"}), status=200)
    else:
        response=Response(json.dumps({"message" : "Name or Email already exists"}), status=401)
    return response

@app.route('/api/points_hours/fetch', methods=["POST", "OPTIONS"])
@cross_origin(support_credentials=True)
def points_hours():
    token=request.get_json()["token"]
    if not checkifloggedin(token):
        return Response(json.dumps({"message" : "user not logged in!"}), status=403)
    if request.method == "OPTIONS":
        return _build_cors_preflight_response()
    token = request.get_json()["token"]
    points = execute_query("SELECT points FROM users WHERE token=%s;", (token,))[0]
    hours = execute_query("SELECT hours FROM users WHERE token=%s;", (token,))[0]
    return Response(json.dumps({"points" : points, "hours" : hours}), status=200)

@app.route('/api/events/getall', methods=["POST", "OPTIONS"])
@cross_origin(support_credentials=True)
def events_calendar_get():
    if request.method == "OPTIONS":
        return _build_cors_preflight_response()
    events=getallevents()
    return jsonify(events)

@app.route('/api/events/addnew', methods=["POST", "OPTIONS"])
@cross_origin(support_credentials=True)
def events_calendar_add():
    if request.method == "OPTIONS":
        return _build_cors_preflight_response()
    token=request.get_json()["token"]
    if not checkifadmin(token):
        return Response(json.dumps({"message" : "admin access only!"}), status=401)
    id = str(uuid.uuid4())
    name = request.get_json()["name"]
    points = request.get_json()["points"]
    hours = request.get_json()["hours"]
    datetime = request.get_json()["datetime"]
    address = request.get_json()["address"]
    description = request.get_json()["description"]
    attendcode = request.get_json()["code"]
    execute_commit_query("INSERT INTO events(name, points, hours, datetime, address, finished, id, signups, attended, description, code) VALUES (%s, %s, %s, %s, %s, False, %s, ''::hstore, ''::hstore, %s, %s);", (name, points, hours, datetime, address, id, description, attendcode))
    return Response(json.dumps({"message" : "New event added!"}), status=200)

@app.route('/api/events/delete', methods=["POST", "OPTIONS"])
@cross_origin(support_credentials=True)
def events_calendar_delete():
    if request.method == "OPTIONS":
        return _build_cors_preflight_response()
    token=request.get_json()["token"]
    if not checkifadmin(token):
        return Response(json.dumps({"message" : "Admin access only!"}), status=401)
    id = request.get_json()["id"]
    execute_commit_query("DELETE FROM events WHERE id = %s;", (id,))
    return Response(json.dumps({"message" : "Event deleted!"}), status=200)

@app.route('/api/events/markfinished', methods=["POST", "OPTIONS"])
@cross_origin(support_credentials=True)
def finish_event():
    if request.method == "OPTIONS":
        return _build_cors_preflight_response()
    token=request.get_json()["token"]
    if not checkifadmin(token):
        return Response(json.dumps({"message" : "Must be an admin to access this!"}), status=401)
    eventid=request.get_json()["eventid"]
    execute_commit_query("UPDATE events SET finished=True WHERE id=%s;", (eventid,))
    return Response(json.dumps({"message": "Event set to finished!"}), status=200)

@app.route('/api/events/signup', methods=["POST", "OPTIONS"])
@cross_origin(support_credentials=True)
def event_signup():
    if request.method == "OPTIONS":
        return _build_cors_preflight_response()
    token=request.get_json()["token"]
    if not checkifloggedin(token):
        return Response(json.dumps({"message" : "Must be logged in!"}), status=401)
    eventid=request.get_json()["eventid"]
    userid = execute_query("SELECT id FROM users WHERE token=%s;", (token,))[0]
    execute_commit_query("UPDATE events SET signups = signups || hstore(%s, '1') WHERE id=%s;", (userid, eventid))
    execute_commit_query("UPDATE users SET signups = signups || hstore(%s, '1') WHERE id=%s;", (eventid, userid))
    return Response(json.dumps({"message" : "Signed up!"}), status=200)

def remove_key_from_hstore(key, hstore):
    return f"{hstore} - '{key}'"

@app.route('/api/events/delete_signup', methods=["POST", "OPTIONS"])
@cross_origin(support_credentials=True)
def event_delete_signup():
    if request.method == "OPTIONS":
        return _build_cors_preflight_response()
    token=request.get_json()["token"]
    if not checkifloggedin(token):
        return Response(json.dumps({"message" : "must be logged in!"}), status=401)
    eventid=request.get_json()["eventid"]
    userid = execute_query("SELECT id FROM users WHERE token=%s;", (token,))[0]
    userid_query = remove_key_from_hstore(userid, "signups")
    eventid_query = remove_key_from_hstore(eventid, "signups")
    execute_commit_query("UPDATE events SET signups = signups - CAST(%s AS TEXT) WHERE id=%s;", (userid, eventid))
    execute_commit_query("UPDATE users SET signups = signups - CAST(%s AS TEXT) WHERE id=%s;", (eventid, userid))
    return Response(json.dumps({"message" : "signup was deleted!"}), status=200)

@app.route('/api/events/status', methods=["POST", "OPTIONS"])
@cross_origin(support_credentials=True)
def event_status():
    if request.method == "OPTIONS":
        return _build_cors_preflight_response()
    token=request.get_json()["token"]
    if not checkifloggedin(token):
        return Response(json.dumps({"message" : "Must be logged in!"}), status=401)
    eventid=request.get_json()["eventid"]
    userid = execute_query("SELECT id FROM users WHERE token=%s;", (token,))[0]
    user_signups = execute_query("SELECT signups ? %s as is_signedup FROM users WHERE id=%s;", (eventid, userid,))[0][0]
    user_attends = execute_query("SELECT attended ? %s as has_attended FROM users WHERE id=%s;", (eventid, userid,))[0][0]
    event_finished=bool(execute_query("SELECT finished FROM events WHERE id=%s;", (eventid,))[0][0])
    if user_attends:
        status = "attended"
    elif event_finished:
        status = "event finished"
    elif user_signups:
        status = "signed up"
    else:
        status = "not signed up"
    return Response(json.dumps({"status" : status}), status=200)

@app.route('/api/events/checkfinished', methods=["POST", "OPTIONS"])
@cross_origin(support_credentials=True)
def check_finished():
    if request.method == "OPTIONS":
        return _build_cors_preflight_response()
    eventid=request.get_json()["eventid"]
    event_finished=bool(execute_query("SELECT finished FROM events WHERE id=%s;", (eventid,))[0][0])
    return Response(json.dumps({"finished" : event_finished}), status=200)

@app.route('/api/events/attendevent', methods=["POST", "OPTIONS"])
@cross_origin(support_credentials=True)
def attend_event():
    if request.method == "OPTIONS":
        return _build_cors_preflight_response()
    token=request.get_json()["token"]
    if not checkifloggedin(token):
        return Response(json.dumps({"message" : "Must be logged in!"}), status=401)
    eventid=request.get_json()["eventid"]
    try:
        attendcode=request.get_json()["code"]
    except:
        return Response(json.dumps({"message" : "Invalid code!"}), status=400)
    correct_code=execute_query("SELECT code FROM events WHERE id=%s;", (eventid,))[0][0]
    if attendcode != correct_code:
        return Response(json.dumps({"message" : "Invalid code!"}), status=400)
    # Check if event is already marked as finished
    event_finished=bool(execute_query("SELECT finished FROM events WHERE id=%s;", (eventid,))[0][0])
    if event_finished:
        return Response(json.dumps({"message" : "Event already finished!"}), status=400)
    # Check if user has already attended the event
    userid = execute_query("SELECT id FROM users WHERE token=%s;", (token,))[0]
    user_attends = execute_query("SELECT attended ? %s as has_attended FROM users WHERE id=%s;", (eventid, userid,))[0][0]
    if user_attends:
        return Response(json.dumps({"message" : "User already attended the event!"}), status=400)
    points_hours = execute_query("SELECT points, hours FROM events WHERE id=%s;", (eventid,))[0]
    execute_commit_query("UPDATE users SET points = points + %s, hours = hours + %s WHERE token=%s;", (points_hours[0], points_hours[1], token))
    execute_commit_query("UPDATE events SET attended = attended || hstore(%s, '1') WHERE id=%s;", (userid, eventid))
    execute_commit_query("UPDATE users SET attended = attended || hstore(%s, '1') WHERE id=%s;", (eventid, userid))
    return Response(json.dumps({"message" : "Event attended!"}), status=200)

@app.route("/api/isauthenticated", methods=["POST", "OPTIONS"])
@cross_origin(support_credentials=True)
def isauthenticated():
    if request.method == "OPTIONS":
        return _build_cors_preflight_response()
    token = request.get_json()["token"]
    return Response(json.dumps({"authenticated" : checkifloggedin(token,)}), status=200)

@app.route("/api/isadmin", methods=["POST", "OPTIONS"])
@cross_origin(support_credentials=True)
def isadmin():
    if request.method == "OPTIONS":
        return _build_cors_preflight_response()
    token = request.get_json()["token"]
    return Response(json.dumps({"authenticated" : checkifadmin(token,)}), status=200)

@app.route("/api/getuserdata", methods=["POST", "OPTIONS"])
@cross_origin(support_credentials=True)
def userdata():
    if request.method == "OPTIONS":
        return _build_cors_preflight_response()
    token = request.get_json()["token"]
    if not checkifloggedin(token):
        return Response(json.dumps({"message" : "must be logged in!"}), status=401)
    data=getuserdata(token)
    return jsonify({"userdata": data}), 200

@app.route('/api/admin/execute_sql', methods=["POST", "OPTIONS"])
@cross_origin(support_credentials=True)
def execute_sql():
    if request.method == "OPTIONS":
        return _build_cors_preflight_response()
    token=request.get_json()["token"]
    if not checkifadmin(token):
        return Response(json.dumps({"message" : "admin access only!"}), status=401)
    query = request.get_json()["query"]
    try:
        cursor = sqlconnection.cursor()
        cursor.execute(query)
        results = cursor.fetchall()
        sqlconnection.commit()
        cursor.close()
        return jsonify({"results" : results}), 200
    except Exception as e:
        sqlconnection.rollback()
        return Response(json.dumps({"error" : str(e)}), status=400)

if __name__ == '__main__':
    app.run(debug=True)