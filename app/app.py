# AJ Barker — D&D 5E Companion
import json, os, random, tempfile
from bson import ObjectId
import bcrypt
from flask import (Flask, render_template, request, send_file,
                   redirect, url_for, flash, jsonify, abort)
from flask_login import LoginManager, UserMixin, login_required, current_user
from pymongo import MongoClient
from pypdf import PdfReader, PdfWriter
from pypdf.generic import BooleanObject, NameObject

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "changeme-in-production")

MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
client = MongoClient(MONGODB_URI)
db = client["5e-database"]

# ── Flask-Login ────────────────────────────────────────────────────────────
login_manager = LoginManager(app)
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access that page."
login_manager.login_message_category = "info"

class User(UserMixin):
    def __init__(self, doc):
        self.id       = str(doc["_id"])
        self.username = doc["username"]
        self.is_admin = doc.get("is_admin", False)
    def get_id(self): return self.id

@login_manager.user_loader
def load_user(user_id):
    try:
        doc = db["users"].find_one({"_id": ObjectId(user_id)})
        return User(doc) if doc else None
    except: return None

# ── Collections ────────────────────────────────────────────────────────────
RACES_TABLE         = "2014-races"
SKILLS_TABLE        = "2014-skills"
CLASSES_TABLE       = "2014-classes"
PROFICIENCIES_TABLE = "2014-proficiencies"
BACKGROUNDS_TABLE   = "2024-backgrounds"
ALIGNMENTS_TABLE    = "2024-alignments"
SUBCLASSES_TABLE    = "2024-subclasses"
CHARACTERS_TABLE    = "characters"

ABILITY_KEYS = ["STR","DEX","CON","INT","WIS","CHA"]

SPELLCASTING_ABILITY = {
    "Bard":"CHA","Cleric":"WIS","Druid":"WIS","Paladin":"CHA",
    "Ranger":"WIS","Sorcerer":"CHA","Warlock":"CHA","Wizard":"INT",
}
CLASS_HIT_DIE = {
    "Barbarian":12,"Bard":8,"Cleric":8,"Druid":8,"Fighter":10,
    "Monk":8,"Paladin":10,"Ranger":10,"Rogue":8,"Sorcerer":6,"Warlock":8,"Wizard":6,
}
standard_abilities = {
    "Barbarian":{"STR":15,"DEX":13,"CON":14,"INT":10,"WIS":12,"CHA":8},
    "Bard":     {"STR":8, "DEX":14,"CON":12,"INT":13,"WIS":10,"CHA":15},
    "Cleric":   {"STR":14,"DEX":8, "CON":13,"INT":10,"WIS":15,"CHA":12},
    "Druid":    {"STR":8, "DEX":12,"CON":14,"INT":13,"WIS":15,"CHA":10},
    "Fighter":  {"STR":15,"DEX":14,"CON":13,"INT":8, "WIS":10,"CHA":12},
    "Monk":     {"STR":12,"DEX":15,"CON":13,"INT":10,"WIS":14,"CHA":8},
    "Paladin":  {"STR":15,"DEX":10,"CON":13,"INT":8, "WIS":12,"CHA":10},
    "Ranger":   {"STR":12,"DEX":15,"CON":13,"INT":8, "WIS":14,"CHA":10},
    "Rogue":    {"STR":12,"DEX":15,"CON":13,"INT":14,"WIS":10,"CHA":8},
    "Sorcerer": {"STR":10,"DEX":13,"CON":14,"INT":8, "WIS":12,"CHA":15},
    "Warlock":  {"STR":8, "DEX":14,"CON":13,"INT":12,"WIS":10,"CHA":15},
    "Wizard":   {"STR":8, "DEX":12,"CON":13,"INT":15,"WIS":14,"CHA":10},
}

# ── Helpers ────────────────────────────────────────────────────────────────
def roll_ability_score():
    rolls = sorted([random.randint(1,6) for _ in range(4)])
    return sum(rolls[1:])

def to_signed(num):
    try: return f"+{int(num)}" if int(num)>0 else str(int(num))
    except: return str(num)

def get_ability_modifier(ability):
    try: return (int(ability)-10)//2
    except: return 0

def get_ability_modifier_str(ability):
    return to_signed(get_ability_modifier(ability))

def get_proficiency_bonus(lvl):
    try: return (max(1,min(20,int(lvl)))-1)//4+2
    except: return 2

def get_all_skills():
    try: return {c["name"]:c["ability_score"]["name"] for c in db[SKILLS_TABLE].find({},{"_id":0})}
    except: return {}

def get_selected_race_obj(race):
    try: return db[RACES_TABLE].find_one({"name":race},{"_id":0})
    except: return None

def get_class_obj(cn):
    try: return db[CLASSES_TABLE].find_one({"name":cn},{"_id":0})
    except: return None

def get_background_obj(bg):
    try: return db[BACKGROUNDS_TABLE].find_one({"name":bg},{"_id":0})
    except: return None

def items_to_string(items):
    return ", ".join(str(i) for i in items)

def get_class_proficiency_options(cn):
    try:
        co = get_class_obj(cn)
        if not co or "proficiency_choices" not in co: return [],0
        count = co["proficiency_choices"][0]["choose"]
        choices = [t["item"]["name"].replace("Skill: ","") for t in co["proficiency_choices"][0]["from"]["options"]]
        return choices,count
    except: return [],0

def validate_ability_score(v,default=10):
    try: return max(1,min(30,int(v)))
    except: return default

def validate_level(v):
    try: return max(1,min(20,int(v)))
    except: return 1

def sanitize_text(v,max_length=100,default="Unknown"):
    if not v: return default
    return str(v).strip()[:max_length]

def calc_max_hp(cn,level,con_score):
    hd=CLASS_HIT_DIE.get(cn,8); cm=get_ability_modifier(con_score)
    return max(1,(hd+cm)+((hd//2+1)+cm)*(level-1))

def get_saving_throws(cn,abilities,prof_bonus):
    try:
        co=get_class_obj(cn)
        profs={st["name"] for st in co.get("saving_throws",[])} if co else set()
    except: profs=set()
    return {k:to_signed(get_ability_modifier(abilities[k])+(prof_bonus if k in profs else 0)) for k in ABILITY_KEYS}

def get_weapon_proficiencies(cn,rn):
    try:
        p=[c["name"] for c in db[PROFICIENCIES_TABLE].find(
            {"type":"Weapons","$or":[{"classes.name":cn},{"races.name":rn}]},{"_id":0,"name":1})]
        return items_to_string(p)
    except: return ""

def get_tool_proficiencies(cn,rn):
    try:
        p=[c["name"] for c in db[PROFICIENCIES_TABLE].find(
            {"type":"Artisan's Tools","$or":[{"classes.name":cn},{"races.name":rn}]},{"_id":0,"name":1})]
        return items_to_string(p)
    except: return ""

def get_class_features_text(cn,level):
    try:
        docs=list(db["2014-features"].find({"class.name":cn,"level":{"$lte":level}},{"_id":0,"name":1,"level":1}).sort("level",1))
        if docs: return "\n".join(f"Lv{f['level']}: {f['name']}" for f in docs[:30])
        co=get_class_obj(cn)
        if co and "features" in co: return "\n".join(f["name"] for f in co["features"][:30])
        return ""
    except: return ""

def get_new_features_at_level(cn,level):
    try: return [f["name"] for f in db["2014-features"].find({"class.name":cn,"level":level},{"_id":0,"name":1})]
    except: return []

def get_spellcasting_fields(cn,abilities,prof_bonus):
    sa=SPELLCASTING_ABILITY.get(cn)
    if not sa: return "","",""
    mod=get_ability_modifier(abilities[sa])
    return sa,str(8+prof_bonus+mod),to_signed(prof_bonus+mod)

def get_background_traits(bg_name):
    try:
        bg=get_background_obj(bg_name)
        if not bg: return ""
        parts=[]
        if "feature" in bg:
            f=bg["feature"]
            if f.get("name"): parts.append(f["name"])
            desc=f.get("desc",[])
            parts.extend(desc[:2] if isinstance(desc,list) else [str(desc)[:300]])
        return "\n".join(parts)[:500]
    except: return ""

def char_access(char,require_owner=False):
    uid=current_user.id
    if str(char.get("owner_id"))==uid: return True
    if require_owner: return False
    return uid in [str(x) for x in char.get("shared_with",[])]

def serialize_char(char):
    char["_id"]=str(char["_id"]); return char

def fill_pdf(character,tmp_file):
    template="/res/DnD_2024_Character-Sheet R3.pdf"
    reader=PdfReader(template); writer=PdfWriter()
    writer.append_pages_from_reader(reader)
    writer._root_object[NameObject("/AcroForm")]=reader.trailer["/Root"]["/AcroForm"]
    writer._root_object["/AcroForm"][NameObject("/NeedAppearances")]=BooleanObject(True)
    name_field=character["Name"]
    if character.get("PlayerName") not in ("Unknown","",None):
        name_field=f"{name_field} ({character['PlayerName']})"
    fd={
        "CharacterName_Field":name_field,"Race_Field":character.get("Race",""),
        "Class_Field":character.get("Class",""),"Subclass_Field":character.get("Subclass",""),
        "Background_Field":character.get("Background",""),"Alignment_Field":character.get("Alignment",""),
        "LVL_Field":str(character.get("Level",1)),"XP_Field":"0",
        "STR_Field":str(character["Abilities"]["STR"]),"DEX_Field":str(character["Abilities"]["DEX"]),
        "CON_Field":str(character["Abilities"]["CON"]),"INT_Field":str(character["Abilities"]["INT"]),
        "WIS_Field":str(character["Abilities"]["WIS"]),"CHA_Field":str(character["Abilities"]["CHA"]),
        "STR_Mod_Field":character["Modifiers"]["STR"],"DEX_Mod_Field":character["Modifiers"]["DEX"],
        "CON_Mod_Field":character["Modifiers"]["CON"],"INT_Mod_Field":character["Modifiers"]["INT"],
        "WIS_Mod_Field":character["Modifiers"]["WIS"],"CHA_Mod_Field":character["Modifiers"]["CHA"],
        "ProficiencyBonus":character.get("ProficiencyBonus",""),
        "Initiative_Field":character.get("Initiative",""),
        "ArmorClass_Field":character.get("ArmorClass",""),
        "Speed_Field":str(character.get("Speed",30)),
        "Size_Field":character.get("Size",""),
        "HP_MAX_Field":character.get("MaxHP",""),"HP_Current_Field":character.get("MaxHP",""),
        "HitDice_Field":character.get("HitDice",""),
        "PassivePerception_Field":character.get("PassivePerception",""),
        "STR_ST_Field":character["SavingThrows"]["STR"],"DEX_ST_Field":character["SavingThrows"]["DEX"],
        "CON_ST_Field":character["SavingThrows"]["CON"],"INT_ST_Field":character["SavingThrows"]["INT"],
        "WIS_ST_Field":character["SavingThrows"]["WIS"],"CHA_ST_Field":character["SavingThrows"]["CHA"],
        "Athletics_Field":character["Skills"].get("Athletics",""),
        "Acrobatics_Field":character["Skills"].get("Acrobatics",""),
        "SleightOfHand_Field":character["Skills"].get("Sleight of Hand",""),
        "Stealth_Field":character["Skills"].get("Stealth",""),
        "Arcana_Field":character["Skills"].get("Arcana",""),
        "History_Field":character["Skills"].get("History",""),
        "Investigation_Field":character["Skills"].get("Investigation",""),
        "Nature_Field":character["Skills"].get("Nature",""),
        "Religion_Field":character["Skills"].get("Religion",""),
        "AnimalHandling_Field":character["Skills"].get("Animal Handling",""),
        "Insight_Field":character["Skills"].get("Insight",""),
        "Medicine_Field":character["Skills"].get("Medicine",""),
        "Perception_Field":character["Skills"].get("Perception",""),
        "Survival_Field":character["Skills"].get("Survival",""),
        "Decption_Field":character["Skills"].get("Deception",""),
        "Intimidation_Field":character["Skills"].get("Intimidation",""),
        "Performance_Field":character["Skills"].get("Performance",""),
        "Persuasion_Field":character["Skills"].get("Persuasion",""),
        "Languages_Field":items_to_string(character.get("Languages",[])),
        "WeaponProficiencies_Field":character.get("WeaponProficiencies",""),
        "ToolProficiencies_Field":character.get("ToolProficiencies",""),
        "Class_Features_Field":character.get("ClassFeatures",""),
        "Spellcasting_MOD":character.get("SpellcastingAbility",""),
        "SpellSave_DC":character.get("SpellSaveDC",""),
        "Spell_ATK_Bonus":character.get("SpellAtkBonus",""),
        "Traits_Field":character.get("BackgroundTraits",""),
    }
    for page in writer.pages:
        writer.update_page_form_field_values(page,fd)
    writer.write(tmp_file)

def build_character_from_form():
    selected_race=sanitize_text(request.form.get("race"),default="")
    all_skills=get_all_skills()
    race_obj=get_selected_race_obj(selected_race)
    lvl=validate_level(request.form.get("LVL"))
    prof_bonus=get_proficiency_bonus(lvl)
    selected_class=sanitize_text(request.form.get("class"),default="")
    selected_bg=sanitize_text(request.form.get("background"),default="")
    abilities={k:validate_ability_score(request.form.get(k)) for k in ABILITY_KEYS}
    modifiers={k:get_ability_modifier_str(abilities[k]) for k in ABILITY_KEYS}
    speed=race_obj.get("speed",30) if race_obj else 30
    size=race_obj.get("size","") if race_obj else ""
    languages=[c["name"] for c in race_obj.get("languages",[])] if race_obj else []
    subclass=sanitize_text(request.form.get("subclass"),default="")
    if subclass.lower()=="none": subclass=""
    dex_mod=get_ability_modifier(abilities["DEX"]); wis_mod=get_ability_modifier(abilities["WIS"])
    hd=CLASS_HIT_DIE.get(selected_class,8)
    sa,sdc,sab=get_spellcasting_fields(selected_class,abilities,prof_bonus)
    character={
        "Name":sanitize_text(request.form.get("CharacterName")),
        "PlayerName":sanitize_text(request.form.get("PlayerName")),
        "Race":selected_race,"Class":selected_class,"Subclass":subclass,
        "Background":selected_bg,"Level":lvl,"ProficiencyBonus":to_signed(prof_bonus),
        "Abilities":abilities,"Modifiers":modifiers,
        "Alignment":sanitize_text(request.form.get("alignment"),default=""),
        "Speed":speed,"Size":size,"Languages":languages,
        "Initiative":to_signed(dex_mod),"ArmorClass":str(10+dex_mod),
        "MaxHP":str(calc_max_hp(selected_class,lvl,abilities["CON"])),
        "HitDice":f"1d{hd}","PassivePerception":str(10+wis_mod),
        "SavingThrows":get_saving_throws(selected_class,abilities,prof_bonus),
        "WeaponProficiencies":get_weapon_proficiencies(selected_class,selected_race),
        "ToolProficiencies":get_tool_proficiencies(selected_class,selected_race),
        "ClassFeatures":get_class_features_text(selected_class,lvl),
        "SpellcastingAbility":sa,"SpellSaveDC":sdc,"SpellAtkBonus":sab,
        "BackgroundTraits":get_background_traits(selected_bg),
        "owner_id":current_user.id,"shared_with":[],
    }
    selected_proficiencies=request.form.getlist("proficiencies")
    character["Skills"]={}
    for skill_name,ability_abbr in all_skills.items():
        mod=get_ability_modifier(abilities[ability_abbr])
        character["Skills"][skill_name]=to_signed(mod+(prof_bonus if skill_name in selected_proficiencies else 0))
    return character

def recalculate_character(char):
    lvl=char["Level"]; abilities=char["Abilities"]
    cn=char["Class"]; rn=char["Race"]
    prof_bonus=get_proficiency_bonus(lvl); old_prof=get_proficiency_bonus(lvl-1)
    all_skills=get_all_skills()
    dex_mod=get_ability_modifier(abilities["DEX"]); wis_mod=get_ability_modifier(abilities["WIS"])
    hd=CLASS_HIT_DIE.get(cn,8)
    sa,sdc,sab=get_spellcasting_fields(cn,abilities,prof_bonus)
    char["ProficiencyBonus"]=to_signed(prof_bonus)
    char["Modifiers"]={k:get_ability_modifier_str(abilities[k]) for k in ABILITY_KEYS}
    char["Initiative"]=to_signed(dex_mod); char["ArmorClass"]=str(10+dex_mod)
    char["MaxHP"]=str(calc_max_hp(cn,lvl,abilities["CON"]))
    char["HitDice"]=f"1d{hd}"; char["PassivePerception"]=str(10+wis_mod)
    char["SavingThrows"]=get_saving_throws(cn,abilities,prof_bonus)
    char["WeaponProficiencies"]=get_weapon_proficiencies(cn,rn)
    char["ToolProficiencies"]=get_tool_proficiencies(cn,rn)
    char["ClassFeatures"]=get_class_features_text(cn,lvl)
    char["SpellcastingAbility"]=sa; char["SpellSaveDC"]=sdc; char["SpellAtkBonus"]=sab
    char["Skills"]={}
    for skill_name,ability_abbr in all_skills.items():
        mod=get_ability_modifier(abilities[ability_abbr])
        old_val=char.get("Skills",{}).get(skill_name,"")
        had_prof=old_val==to_signed(mod+old_prof)
        char["Skills"][skill_name]=to_signed(mod+(prof_bonus if had_prof else 0))
    return char

# ── Register blueprints ────────────────────────────────────────────────────
from auth import auth_bp
from maps import maps_bp
from sessions_bp import sessions_bp
app.register_blueprint(auth_bp)
app.register_blueprint(maps_bp)
app.register_blueprint(sessions_bp)

# ── Routes ─────────────────────────────────────────────────────────────────
@app.route("/")
def home_page():
    return render_template("home.html")

@app.route("/builder", methods=["GET","POST"])
@login_required
def character_builder():
    try:
        races=sorted([r["name"] for r in db[RACES_TABLE].find({},{"_id":0,"name":1})])
        classes=sorted([c["name"] for c in db[CLASSES_TABLE].find({},{"_id":0,"name":1})])
        backgrounds=sorted([b["name"] for b in db[BACKGROUNDS_TABLE].find({},{"_id":0,"name":1})])
        alignments=sorted([b["name"] for b in db[ALIGNMENTS_TABLE].find({},{"_id":0,"name":1})])
    except Exception as e:
        app.logger.error("DB error: %s",e); return "Database unavailable.",503

    abilities={k:10 for k in ABILITY_KEYS}; lvl=1
    character_name="Unknown"; player_name="Unknown"
    selected_race=races[0] if races else ""
    selected_class=classes[0] if classes else ""
    selected_bg=backgrounds[0] if backgrounds else ""
    selected_alignment=alignments[0] if alignments else ""
    selected_subclass=""; selected_profs=[]; character_json=None
    subclasses=["None"]+[c["name"] for c in db[SUBCLASSES_TABLE].find({"class.name":selected_class},{"_id":0,"name":1})]
    prof_choices,prof_count=get_class_proficiency_options(selected_class)

    if request.method=="POST":
        character=build_character_from_form()
        abilities=character["Abilities"]; lvl=character["Level"]
        character_name=character["Name"]; player_name=character["PlayerName"]
        selected_class=character["Class"]; selected_race=character["Race"]
        selected_profs=request.form.getlist("proficiencies")
        subclasses=["None"]+[c["name"] for c in db[SUBCLASSES_TABLE].find({"class.name":selected_class},{"_id":0,"name":1})]
        prof_choices,prof_count=get_class_proficiency_options(selected_class)
        if   "Generate Abilities" in request.form: abilities={k:roll_ability_score() for k in ABILITY_KEYS}
        elif "Standard Abilities" in request.form:
            if selected_class in standard_abilities: abilities=standard_abilities[selected_class]
        elif "Create Character"   in request.form: character_json=json.dumps(character,indent=2,default=str)
        elif "Save Character"     in request.form:
            db[CHARACTERS_TABLE].insert_one(character)
            flash(f"{character['Name']} saved!","success")
            return redirect(url_for("characters_list"))
        elif "Save PDF" in request.form:
            try:
                with tempfile.NamedTemporaryFile(delete=False,suffix=".pdf") as tmp:
                    fill_pdf(character,tmp)
                return send_file(tmp.name,as_attachment=True,download_name="character.pdf")
            except FileNotFoundError: return "PDF template not found.",500
            except Exception as e:
                app.logger.error("PDF error: %s",e); return "Error generating PDF.",500

    return render_template("index.html",
                           races=races, selected_race=selected_race,
                           classes=classes, selected_class=selected_class,
                           subclasses=subclasses, selected_subclass=selected_subclass,
                           backgrounds=backgrounds, selected_background=selected_bg,
                           alignments=alignments, selected_alignment=selected_alignment,
                           PlayerName=player_name, proficiency_choices=prof_choices,
                           proficiency_count=prof_count, selected_profs=selected_profs,
                           CharacterName=character_name, LVL=lvl,
                           STR=abilities["STR"], DEX=abilities["DEX"], CON=abilities["CON"],
                           INT=abilities["INT"], WIS=abilities["WIS"], CHA=abilities["CHA"],
                           character_json=character_json, edit_mode=False, edit_char_id=None)

@app.route("/characters")
@login_required
def characters_list():
    uid=current_user.id
    chars=list(db[CHARACTERS_TABLE].find({"$or":[{"owner_id":uid},{"shared_with":uid}]}))
    for c in chars: serialize_char(c)
    return render_template("characters.html", characters=chars, uid=uid)

@app.route("/characters/<char_id>")
@login_required
def character_detail(char_id):
    char=db[CHARACTERS_TABLE].find_one({"_id":ObjectId(char_id)})
    if not char or not char_access(char): abort(403)
    serialize_char(char)
    is_owner=str(char.get("owner_id"))==current_user.id
    shared_users=[]
    if is_owner:
        for uid in char.get("shared_with",[]):
            u=db["users"].find_one({"_id":ObjectId(uid)},{"username":1})
            if u: shared_users.append({"id":str(u["_id"]),"username":u["username"]})
    return render_template("character_detail.html", char=char, is_owner=is_owner, shared_users=shared_users)

@app.route("/characters/<char_id>/edit",methods=["GET","POST"])
@login_required
def character_edit(char_id):
    char=db[CHARACTERS_TABLE].find_one({"_id":ObjectId(char_id)})
    if not char or not char_access(char,require_owner=True): abort(403)
    serialize_char(char)
    try:
        races=sorted([r["name"] for r in db[RACES_TABLE].find({},{"_id":0,"name":1})])
        classes=sorted([c["name"] for c in db[CLASSES_TABLE].find({},{"_id":0,"name":1})])
        backgrounds=sorted([b["name"] for b in db[BACKGROUNDS_TABLE].find({},{"_id":0,"name":1})])
        alignments=sorted([b["name"] for b in db[ALIGNMENTS_TABLE].find({},{"_id":0,"name":1})])
    except: return "Database unavailable.",503
    subclasses=["None"]+[c["name"] for c in db[SUBCLASSES_TABLE].find({"class.name":char["Class"]},{"_id":0,"name":1})]
    prof_choices,prof_count=get_class_proficiency_options(char["Class"])
    all_skills=get_all_skills()
    selected_profs=[s for s,v in char.get("Skills",{}).items()
        if v==to_signed(get_ability_modifier(char["Abilities"].get(all_skills.get(s,"STR"),10))+get_proficiency_bonus(char["Level"]))]
    if request.method=="POST":
        updated=build_character_from_form()
        updated["owner_id"]=char["owner_id"]; updated["shared_with"]=char.get("shared_with",[])
        if "save_copy" in request.form:
            updated["Name"]=updated["Name"]+" (Copy)"
            db[CHARACTERS_TABLE].insert_one(updated)
            flash(f"Saved copy: {updated['Name']}","success")
            return redirect(url_for("characters_list"))
        else:
            db[CHARACTERS_TABLE].replace_one({"_id":ObjectId(char_id)},updated)
            flash("Character updated.","success")
            return redirect(url_for("character_detail",char_id=char_id))
    a=char["Abilities"]
    return render_template("index.html",
                           races=races, selected_race=char["Race"],
                           classes=classes, selected_class=char["Class"],
                           subclasses=subclasses, selected_subclass=char.get("Subclass",""),
                           backgrounds=backgrounds, selected_background=char.get("Background",""),
                           alignments=alignments, selected_alignment=char.get("Alignment",""),
                           PlayerName=char.get("PlayerName",""), proficiency_choices=prof_choices,
                           proficiency_count=prof_count, selected_profs=selected_profs,
                           CharacterName=char.get("Name",""), LVL=char.get("Level",1),
                           STR=a["STR"], DEX=a["DEX"], CON=a["CON"], INT=a["INT"], WIS=a["WIS"], CHA=a["CHA"],
                           character_json=None, edit_mode=True, edit_char_id=char_id)

@app.route("/characters/<char_id>/levelup",methods=["GET","POST"])
@login_required
def character_levelup(char_id):
    char=db[CHARACTERS_TABLE].find_one({"_id":ObjectId(char_id)})
    if not char or not char_access(char,require_owner=True): abort(403)
    serialize_char(char)
    if char["Level"]>=20:
        flash(f"{char['Name']} is already level 20.","info")
        return redirect(url_for("character_detail",char_id=char_id))
    new_level=char["Level"]+1; new_prof=get_proficiency_bonus(new_level)
    hd=CLASS_HIT_DIE.get(char["Class"],8); con_mod=get_ability_modifier(char["Abilities"]["CON"])
    hp_avg=(hd//2+1)+con_mod; new_max_hp_avg=calc_max_hp(char["Class"],new_level,char["Abilities"]["CON"])
    changes=[
        {"label":"Level","old":char["Level"],"new":new_level},
        {"label":"Proficiency Bonus","old":char["ProficiencyBonus"],"new":to_signed(new_prof)},
        {"label":"Max HP (avg)","old":char["MaxHP"],"new":str(new_max_hp_avg)},
    ]
    sa=SPELLCASTING_ABILITY.get(char["Class"])
    if sa:
        mod=get_ability_modifier(char["Abilities"][sa])
        new_dc=str(8+new_prof+mod); new_atk=to_signed(new_prof+mod)
        if char.get("SpellSaveDC")!=new_dc:   changes.append({"label":"Spell Save DC","old":char.get("SpellSaveDC",""),"new":new_dc})
        if char.get("SpellAtkBonus")!=new_atk: changes.append({"label":"Spell Atk Bonus","old":char.get("SpellAtkBonus",""),"new":new_atk})
    new_features=get_new_features_at_level(char["Class"],new_level)
    if request.method=="POST":
        hp_method=request.form.get("hp_method","avg")
        if hp_method=="avg":
            new_hp=new_max_hp_avg
        elif hp_method=="manual":
            try: new_hp=int(char["MaxHP"])+max(1,int(request.form.get("manual_hp",1)))
            except: new_hp=new_max_hp_avg
        else:  # roll
            roll=random.randint(1,hd)+con_mod; gained=max(1,roll)
            new_hp=int(char["MaxHP"])+gained
            flash(f"HP roll: d{hd} → {roll} (CON {to_signed(con_mod)}) = +{gained} HP","info")
        char["Level"]=new_level; char["MaxHP"]=str(new_hp)
        updated=recalculate_character(char)
        updated["MaxHP"]=str(new_hp)  # preserve chosen HP
        doc_id=updated.pop("_id")
        db[CHARACTERS_TABLE].replace_one({"_id":ObjectId(doc_id)},updated)
        flash(f"{char['Name']} is now level {new_level}! 🎉","success")
        return redirect(url_for("character_detail",char_id=char_id))
    return render_template("levelup.html",
                           char=char, new_level=new_level, changes=changes,
                           hp_avg=hp_avg, hp_avg_total=new_max_hp_avg,
                           con_mod=to_signed(con_mod), hit_die=hd, new_features=new_features)

@app.route("/characters/<char_id>/export_pdf")
@login_required
def character_export_pdf(char_id):
    char=db[CHARACTERS_TABLE].find_one({"_id":ObjectId(char_id)})
    if not char or not char_access(char): abort(403)
    try:
        with tempfile.NamedTemporaryFile(delete=False,suffix=".pdf") as tmp:
            fill_pdf(char,tmp)
        safe_name=char.get("Name","character").replace(" ","_")
        return send_file(tmp.name,as_attachment=True,download_name=f"{safe_name}.pdf")
    except Exception as e:
        app.logger.error("PDF export error: %s",e)
        flash("Error exporting PDF.","error")
        return redirect(url_for("character_detail",char_id=char_id))

@app.route("/characters/<char_id>/share",methods=["POST"])
@login_required
def character_share(char_id):
    char=db[CHARACTERS_TABLE].find_one({"_id":ObjectId(char_id)})
    if not char or not char_access(char,require_owner=True): abort(403)
    username=request.form.get("username","").strip()
    target=db["users"].find_one({"username":username})
    if not target: flash(f"User '{username}' not found.","error")
    elif str(target["_id"])==current_user.id: flash("You can't share with yourself.","error")
    else:
        db[CHARACTERS_TABLE].update_one({"_id":ObjectId(char_id)},{"$addToSet":{"shared_with":str(target["_id"])}})
        flash(f"Shared with {username}.","success")
    return redirect(url_for("character_detail",char_id=char_id))

@app.route("/characters/<char_id>/unshare/<uid>",methods=["POST"])
@login_required
def character_unshare(char_id,uid):
    char=db[CHARACTERS_TABLE].find_one({"_id":ObjectId(char_id)})
    if not char or not char_access(char,require_owner=True): abort(403)
    db[CHARACTERS_TABLE].update_one({"_id":ObjectId(char_id)},{"$pull":{"shared_with":uid}})
    flash("Access removed.","success")
    return redirect(url_for("character_detail",char_id=char_id))

@app.route("/characters/<char_id>/delete",methods=["POST"])
@login_required
def character_delete(char_id):
    char=db[CHARACTERS_TABLE].find_one({"_id":ObjectId(char_id)})
    if not char or not char_access(char,require_owner=True):
        return jsonify({"ok":False}),403
    db[CHARACTERS_TABLE].delete_one({"_id":ObjectId(char_id)})
    return jsonify({"ok":True})

@app.route("/dice")
def dice_roller():
    return render_template("dice.html")

if __name__=="__main__":
    debug_mode=os.environ.get("FLASK_DEBUG","false").lower()=="true"
    app.run(host="0.0.0.0",port=5000,debug=debug_mode)
