import os
from datetime import datetime
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, jsonify, abort)
from flask_login import login_required, current_user
from pymongo import MongoClient
from bson import ObjectId

sessions_bp = Blueprint("sessions", __name__, url_prefix="/sessions")

_client = None
def get_db():
    global _client
    if _client is None:
        _client = MongoClient(os.environ.get("MONGODB_URI","mongodb://localhost:27017"))
    return _client["5e-database"]

SESSIONS_TABLE   = "game_sessions"
CHARACTERS_TABLE = "characters"
MAPS_TABLE       = "maps"

def is_dm(session, uid):
    return str(session.get("dm_id")) == uid

def in_session(session, uid):
    return is_dm(session, uid) or uid in [str(x) for x in session.get("players",[])]

# ── Routes ─────────────────────────────────────────────────────────────────

@sessions_bp.route("/")
@login_required
def sessions_list():
    db = get_db()
    uid = current_user.id
    my_sessions = list(db[SESSIONS_TABLE].find({
        "$or":[{"dm_id":uid},{"players":uid}]
    }))
    for s in my_sessions: s["_id"] = str(s["_id"])
    return render_template("sessions/list.html", sessions=my_sessions, uid=uid)

@sessions_bp.route("/new", methods=["GET","POST"])
@login_required
def session_new():
    db = get_db()
    if request.method == "POST":
        name = request.form.get("name","").strip()[:80]
        if not name:
            flash("Session name required.","error")
            return redirect(url_for("sessions.session_new"))
        maps = list(db[MAPS_TABLE].find({"owner_id":current_user.id},{"_id":1,"name":1}))
        map_id = request.form.get("map_id","")
        doc = {
            "name": name,
            "dm_id": current_user.id,
            "players": [],
            "invited": [],
            "map_id": map_id if map_id else None,
            "visible_cells": [],   # cells players can see
            "fog_enabled": True,
            "chat": [],
            "shared_chars": {},    # {player_uid: [char_id, ...]}
            "created_at": datetime.utcnow(),
        }
        result = db[SESSIONS_TABLE].insert_one(doc)
        flash(f"Session '{name}' created!","success")
        return redirect(url_for("sessions.session_dm",session_id=str(result.inserted_id)))
    maps = list(db[MAPS_TABLE].find({"owner_id":current_user.id},{"_id":1,"name":1}))
    for m in maps: m["_id"] = str(m["_id"])
    return render_template("sessions/new.html", maps=maps)

@sessions_bp.route("/<session_id>")
@login_required
def session_view(session_id):
    db = get_db()
    sess = db[SESSIONS_TABLE].find_one({"_id":ObjectId(session_id)})
    if not sess or not in_session(sess, current_user.id): abort(403)
    if is_dm(sess, current_user.id):
        return redirect(url_for("sessions.session_dm", session_id=session_id))
    return redirect(url_for("sessions.session_player", session_id=session_id))

@sessions_bp.route("/<session_id>/dm")
@login_required
def session_dm(session_id):
    db = get_db()
    sess = db[SESSIONS_TABLE].find_one({"_id":ObjectId(session_id)})
    if not sess or not is_dm(sess, current_user.id): abort(403)
    sess["_id"] = str(sess["_id"])

    map_data = None
    if sess.get("map_id"):
        try:
            map_data = db[MAPS_TABLE].find_one({"_id":ObjectId(sess["map_id"])})
            if map_data: map_data["_id"] = str(map_data["_id"])
        except: pass

    # Gather player info
    players_info = []
    for pid in sess.get("players",[]):
        u = db["users"].find_one({"_id":ObjectId(pid)},{"username":1})
        if u:
            chars = []
            for cid in sess.get("shared_chars",{}).get(pid,[]):
                try:
                    c = db[CHARACTERS_TABLE].find_one({"_id":ObjectId(cid)},{"Name":1,"Class":1,"Level":1})
                    if c: chars.append({"id":str(c["_id"]),"name":c["Name"],"class":c["Class"],"level":c["Level"]})
                except: pass
            players_info.append({"id":pid,"username":u["username"],"chars":chars})

    return render_template("sessions/dm.html",
        sess=sess, map_data=map_data, players_info=players_info)

@sessions_bp.route("/<session_id>/player")
@login_required
def session_player(session_id):
    db = get_db()
    sess = db[SESSIONS_TABLE].find_one({"_id":ObjectId(session_id)})
    if not sess or not in_session(sess, current_user.id): abort(403)
    sess["_id"] = str(sess["_id"])

    map_data = None
    if sess.get("map_id"):
        try:
            map_data = db[MAPS_TABLE].find_one({"_id":ObjectId(sess["map_id"])})
            if map_data: map_data["_id"] = str(map_data["_id"])
        except: pass

    # Player's own characters
    uid = current_user.id
    my_chars = list(db[CHARACTERS_TABLE].find({"owner_id":uid},{"_id":1,"Name":1,"Class":1,"Level":1}))
    for c in my_chars: c["_id"] = str(c["_id"])

    shared_char_ids = sess.get("shared_chars",{}).get(uid,[])

    return render_template("sessions/player.html",
        sess=sess, map_data=map_data,
        my_chars=my_chars, shared_char_ids=shared_char_ids)

# ── API endpoints ──────────────────────────────────────────────────────────

@sessions_bp.route("/<session_id>/invite", methods=["POST"])
@login_required
def session_invite(session_id):
    db = get_db()
    sess = db[SESSIONS_TABLE].find_one({"_id":ObjectId(session_id)})
    if not sess or not is_dm(sess, current_user.id): abort(403)
    username = request.form.get("username","").strip()
    target = db["users"].find_one({"username":username})
    if not target: flash(f"User '{username}' not found.","error")
    else:
        tid = str(target["_id"])
        db[SESSIONS_TABLE].update_one({"_id":ObjectId(session_id)},{"$addToSet":{"invited":tid}})
        flash(f"Invited {username}.","success")
    return redirect(url_for("sessions.session_dm",session_id=session_id))

@sessions_bp.route("/<session_id>/join", methods=["POST"])
@login_required
def session_join(session_id):
    db = get_db()
    sess = db[SESSIONS_TABLE].find_one({"_id":ObjectId(session_id)})
    if not sess: abort(404)
    uid = current_user.id
    if uid not in sess.get("invited",[]) and not is_dm(sess,uid):
        flash("You haven't been invited to this session.","error")
        return redirect(url_for("sessions.sessions_list"))
    db[SESSIONS_TABLE].update_one({"_id":ObjectId(session_id)},
        {"$addToSet":{"players":uid},"$pull":{"invited":uid}})
    flash(f"Joined session '{sess['name']}'!","success")
    return redirect(url_for("sessions.session_player",session_id=session_id))

@sessions_bp.route("/<session_id>/share_char", methods=["POST"])
@login_required
def session_share_char(session_id):
    db = get_db()
    sess = db[SESSIONS_TABLE].find_one({"_id":ObjectId(session_id)})
    if not sess or not in_session(sess, current_user.id): abort(403)
    uid = current_user.id
    char_id = request.form.get("char_id","")
    char = db[CHARACTERS_TABLE].find_one({"_id":ObjectId(char_id)})
    if not char or str(char.get("owner_id")) != uid:
        flash("Character not found or not yours.","error")
    else:
        db[SESSIONS_TABLE].update_one({"_id":ObjectId(session_id)},
            {"$addToSet":{f"shared_chars.{uid}":char_id}})
        flash(f"Shared {char['Name']} with DM.","success")
    return redirect(url_for("sessions.session_player",session_id=session_id))

@sessions_bp.route("/<session_id>/unshare_char", methods=["POST"])
@login_required
def session_unshare_char(session_id):
    db = get_db()
    sess = db[SESSIONS_TABLE].find_one({"_id":ObjectId(session_id)})
    if not sess or not in_session(sess, current_user.id): abort(403)
    uid = current_user.id
    char_id = request.form.get("char_id","")
    db[SESSIONS_TABLE].update_one({"_id":ObjectId(session_id)},
        {"$pull":{f"shared_chars.{uid}":char_id}})
    flash("Character unshared.","success")
    return redirect(url_for("sessions.session_player",session_id=session_id))

@sessions_bp.route("/<session_id>/fog", methods=["POST"])
@login_required
def session_fog(session_id):
    """DM updates fog of war — receives list of revealed cell keys."""
    db = get_db()
    sess = db[SESSIONS_TABLE].find_one({"_id":ObjectId(session_id)})
    if not sess or not is_dm(sess, current_user.id):
        return jsonify({"ok":False}), 403
    data = request.get_json()
    db[SESSIONS_TABLE].update_one({"_id":ObjectId(session_id)},
        {"$set":{"visible_cells":data.get("visible_cells",[]),"fog_enabled":data.get("fog_enabled",True)}})
    return jsonify({"ok":True})

@sessions_bp.route("/<session_id>/state")
@login_required
def session_state(session_id):
    """Polling endpoint — returns current fog + marker state."""
    db = get_db()
    sess = db[SESSIONS_TABLE].find_one({"_id":ObjectId(session_id)},
        {"visible_cells":1,"fog_enabled":1,"map_id":1})
    if not sess or not in_session(db[SESSIONS_TABLE].find_one({"_id":ObjectId(session_id)}), current_user.id):
        return jsonify({"ok":False}), 403
    return jsonify({
        "ok": True,
        "visible_cells": sess.get("visible_cells",[]),
        "fog_enabled": sess.get("fog_enabled",True),
    })

@sessions_bp.route("/<session_id>/chat", methods=["POST"])
@login_required
def session_chat(session_id):
    db = get_db()
    sess = db[SESSIONS_TABLE].find_one({"_id":ObjectId(session_id)})
    if not sess or not in_session(sess, current_user.id): abort(403)
    msg = request.get_json().get("message","").strip()[:500]
    if msg:
        entry = {"uid":current_user.id,"username":current_user.username,
                 "message":msg,"ts":datetime.utcnow().isoformat()}
        db[SESSIONS_TABLE].update_one({"_id":ObjectId(session_id)},
            {"$push":{"chat":{"$each":[entry],"$slice":-200}}})
    return jsonify({"ok":True})

@sessions_bp.route("/<session_id>/chat/poll")
@login_required
def session_chat_poll(session_id):
    db = get_db()
    sess = db[SESSIONS_TABLE].find_one({"_id":ObjectId(session_id)},{"chat":1})
    if not sess: return jsonify([])
    chat = sess.get("chat",[])[-50:]
    return jsonify(chat)

@sessions_bp.route("/<session_id>/delete", methods=["POST"])
@login_required
def session_delete(session_id):
    db = get_db()
    sess = db[SESSIONS_TABLE].find_one({"_id":ObjectId(session_id)})
    if not sess or not is_dm(sess, current_user.id):
        return jsonify({"ok":False}), 403
    db[SESSIONS_TABLE].delete_one({"_id":ObjectId(session_id)})
    return jsonify({"ok":True})
