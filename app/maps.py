import os, io, json, base64
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, jsonify, send_file, abort, current_app)
from flask_login import login_required, current_user
from pymongo import MongoClient
from bson import ObjectId
from PIL import Image, ImageDraw, ImageFont

maps_bp = Blueprint("maps", __name__, url_prefix="/maps")

_client = None
def get_db():
    global _client
    if _client is None:
        _client = MongoClient(os.environ.get("MONGODB_URI","mongodb://localhost:27017"))
    return _client["5e-database"]

MAPS_TABLE  = "maps"
TILES_TABLE = "custom_tiles"
TILE_SIZE   = 48          # px per cell for export
UPLOAD_DIR  = "/app/static/tiles"

# ── Built-in tile definitions ──────────────────────────────────────────────
BUILTIN_TILES = [
    {"id":"dungeon",  "label":"Dungeon",  "color":"#2a2a3e","icon":"⬛","category":"terrain"},
    {"id":"floor",    "label":"Floor",    "color":"#c8b08a","icon":"⬜","category":"terrain"},
    {"id":"forest",   "label":"Forest",   "color":"#1a4a1a","icon":"🌲","category":"terrain"},
    {"id":"road",     "label":"Road",     "color":"#8a7560","icon":"🛤","category":"terrain"},
    {"id":"water",    "label":"Water",    "color":"#1a4a8a","icon":"🌊","category":"terrain"},
    {"id":"lava",     "label":"Lava",     "color":"#c04010","icon":"🔥","category":"terrain"},
    {"id":"wall",     "label":"Wall",     "color":"#555555","icon":"🧱","category":"structure"},
    {"id":"cliff",    "label":"Cliff",    "color":"#6a5a40","icon":"⛰","category":"structure"},
    {"id":"stairs_up","label":"Stairs ↑", "color":"#a09060","icon":"🔼","category":"structure"},
    {"id":"stairs_dn","label":"Stairs ↓", "color":"#706040","icon":"🔽","category":"structure"},
    {"id":"door",     "label":"Door",     "color":"#8a6030","icon":"🚪","category":"structure"},
    {"id":"trap",     "label":"Trap",     "color":"#8a1a1a","icon":"⚠","category":"special"},
    {"id":"chest",    "label":"Chest",    "color":"#c8a020","icon":"📦","category":"special"},
    {"id":"altar",    "label":"Altar",    "color":"#8060a0","icon":"🏛","category":"special"},
    {"id":"campfire", "label":"Campfire", "color":"#c06020","icon":"🔥","category":"special"},
    {"id":"void",     "label":"Empty",    "color":"transparent","icon":"","category":"utility"},
]

def get_all_tiles(db):
    tiles = list(BUILTIN_TILES)
    custom = list(db[TILES_TABLE].find({}, {"_id":1,"id":1,"label":1,"color":1,"icon":1,"category":1,"image_data":1}))
    for t in custom:
        t["_id"] = str(t["_id"])
        t["custom"] = True
    tiles += custom
    return tiles

def map_access(m, require_owner=False):
    uid = current_user.id
    if str(m.get("owner_id")) == uid: return True
    if require_owner: return False
    return uid in [str(x) for x in m.get("shared_with",[])]

# ── Routes ─────────────────────────────────────────────────────────────────

@maps_bp.route("/")
@login_required
def maps_list():
    db = get_db()
    uid = current_user.id
    maps = list(db[MAPS_TABLE].find({"$or":[{"owner_id":uid},{"shared_with":uid}]},
                                    {"_id":1,"name":1,"width":1,"height":1,"owner_id":1}))
    for m in maps: m["_id"] = str(m["_id"])
    return render_template("maps/list.html", maps=maps, uid=uid)

@maps_bp.route("/new")
@login_required
def map_new():
    db = get_db()
    tiles = get_all_tiles(db)
    return render_template("maps/builder.html", map=None, tiles=tiles, map_json="null")

@maps_bp.route("/<map_id>")
@login_required
def map_edit(map_id):
    db = get_db()
    m = db[MAPS_TABLE].find_one({"_id": ObjectId(map_id)})
    if not m or not map_access(m): abort(403)
    m["_id"] = str(m["_id"])
    tiles = get_all_tiles(db)
    return render_template("maps/builder.html", map=m, tiles=tiles, map_json=json.dumps(m))

@maps_bp.route("/save", methods=["POST"])
@login_required
def map_save():
    db = get_db()
    data = request.get_json()
    if not data: return jsonify({"ok":False,"error":"No data"}), 400
    map_id = data.pop("_id", None)
    data["owner_id"] = current_user.id
    data.setdefault("shared_with", [])
    if map_id:
        m = db[MAPS_TABLE].find_one({"_id": ObjectId(map_id)})
        if not m or not map_access(m, require_owner=True):
            return jsonify({"ok":False,"error":"Forbidden"}), 403
        db[MAPS_TABLE].replace_one({"_id": ObjectId(map_id)}, data)
        return jsonify({"ok":True, "map_id": map_id})
    else:
        result = db[MAPS_TABLE].insert_one(data)
        return jsonify({"ok":True, "map_id": str(result.inserted_id)})

@maps_bp.route("/<map_id>/delete", methods=["POST"])
@login_required
def map_delete(map_id):
    db = get_db()
    m = db[MAPS_TABLE].find_one({"_id": ObjectId(map_id)})
    if not m or not map_access(m, require_owner=True):
        return jsonify({"ok":False}), 403
    db[MAPS_TABLE].delete_one({"_id": ObjectId(map_id)})
    return jsonify({"ok":True})

@maps_bp.route("/<map_id>/export_png")
@login_required
def map_export_png(map_id):
    db = get_db()
    m = db[MAPS_TABLE].find_one({"_id": ObjectId(map_id)})
    if not m or not map_access(m): abort(403)

    cells  = m.get("cells", {})
    marks  = m.get("markers", [])
    width  = m.get("width",  20)
    height = m.get("height", 20)
    ts     = TILE_SIZE
    all_tiles = {t["id"]: t for t in get_all_tiles(db)}

    img    = Image.new("RGBA", (width*ts, height*ts), (30,25,15,255))
    draw   = ImageDraw.Draw(img)

    # Draw tiles
    for key, tile_id in cells.items():
        try:
            cx, cy = map(int, key.split(","))
        except: continue
        tile = all_tiles.get(tile_id)
        if not tile or tile_id == "void": continue
        x1,y1 = cx*ts, cy*ts; x2,y2 = x1+ts-1, y1+ts-1
        color = tile.get("color","#444")
        if color == "transparent": continue
        # Try to decode custom image
        if tile.get("image_data"):
            try:
                img_data = base64.b64decode(tile["image_data"].split(",")[-1])
                tile_img = Image.open(io.BytesIO(img_data)).resize((ts,ts)).convert("RGBA")
                img.paste(tile_img, (x1,y1), tile_img)
                continue
            except: pass
        try: draw.rectangle([x1,y1,x2,y2], fill=color)
        except: draw.rectangle([x1,y1,x2,y2], fill="#444444")
        # Grid line
        draw.rectangle([x1,y1,x2,y2], outline="#00000044", width=1)

    # Draw markers
    for marker in marks:
        cx = marker.get("x",0); cy = marker.get("y",0)
        mtype = marker.get("type","player")
        label = marker.get("label","?")[:2]
        x1,y1 = cx*ts+2, cy*ts+2; x2,y2 = x1+ts-4, y1+ts-4
        color = "#4488ff" if mtype=="player" else "#ff4444" if mtype=="npc" else "#ffcc44"
        draw.ellipse([x1,y1,x2,y2], fill=color, outline="#ffffff", width=2)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
        except: font = ImageFont.load_default()
        bbox = draw.textbbox((0,0), label, font=font)
        tw,th = bbox[2]-bbox[0], bbox[3]-bbox[1]
        tx = x1 + (ts-4-tw)//2; ty = y1 + (ts-4-th)//2
        draw.text((tx,ty), label, fill="#ffffff", font=font)

    # Grid overlay
    for cx in range(width+1):
        draw.line([(cx*ts,0),(cx*ts,height*ts)], fill="#00000033", width=1)
    for cy in range(height+1):
        draw.line([(0,cy*ts),(width*ts,cy*ts)], fill="#00000033", width=1)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    safe_name = m.get("name","map").replace(" ","_")
    return send_file(buf, mimetype="image/png", as_attachment=True, download_name=f"{safe_name}.png")

# ── Tile management ────────────────────────────────────────────────────────

@maps_bp.route("/tiles")
@login_required
def tiles_list():
    db = get_db()
    tiles = get_all_tiles(db)
    return render_template("maps/tiles.html", tiles=tiles)

@maps_bp.route("/tiles/save", methods=["POST"])
@login_required
def tile_save():
    db = get_db()
    tile_id_param = request.form.get("tile_id","").strip()
    label    = request.form.get("label","").strip()[:40]
    color    = request.form.get("color","#888888")
    icon     = request.form.get("icon","")[:4]
    category = request.form.get("category","terrain")
    image_data = None

    if "image" in request.files:
        f = request.files["image"]
        if f and f.filename:
            try:
                img = Image.open(f).resize((TILE_SIZE*2, TILE_SIZE*2)).convert("RGBA")
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                b64 = base64.b64encode(buf.getvalue()).decode()
                image_data = f"data:image/png;base64,{b64}"
            except Exception as e:
                flash(f"Image error: {e}", "error")

    doc = {"label":label,"color":color,"icon":icon,"category":category,
           "owner_id":current_user.id}
    if image_data: doc["image_data"] = image_data

    if tile_id_param:
        existing = db[TILES_TABLE].find_one({"_id":ObjectId(tile_id_param)})
        if existing and str(existing.get("owner_id")) == current_user.id:
            doc["id"] = existing.get("id", str(existing["_id"]))
            db[TILES_TABLE].replace_one({"_id":ObjectId(tile_id_param)}, doc)
            flash("Tile updated.", "success")
        else:
            flash("Tile not found or no permission.", "error")
    else:
        result = db[TILES_TABLE].insert_one(doc)
        db[TILES_TABLE].update_one({"_id":result.inserted_id},{"$set":{"id":str(result.inserted_id)}})
        flash(f"Tile '{label}' created.", "success")
    return redirect(url_for("maps.tiles_list"))

@maps_bp.route("/tiles/<tile_id>/delete", methods=["POST"])
@login_required
def tile_delete(tile_id):
    db = get_db()
    t = db[TILES_TABLE].find_one({"_id":ObjectId(tile_id)})
    if not t or str(t.get("owner_id")) != current_user.id:
        return jsonify({"ok":False}), 403
    db[TILES_TABLE].delete_one({"_id":ObjectId(tile_id)})
    return jsonify({"ok":True})

@maps_bp.route("/<map_id>/share", methods=["POST"])
@login_required
def map_share(map_id):
    db = get_db()
    m = db[MAPS_TABLE].find_one({"_id":ObjectId(map_id)})
    if not m or not map_access(m,require_owner=True): abort(403)
    username = request.form.get("username","").strip()
    target = db["users"].find_one({"username":username})
    if not target: flash(f"User '{username}' not found.","error")
    else:
        db[MAPS_TABLE].update_one({"_id":ObjectId(map_id)},{"$addToSet":{"shared_with":str(target["_id"])}})
        flash(f"Map shared with {username}.","success")
    return redirect(url_for("maps.map_edit",map_id=map_id))
