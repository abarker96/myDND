# AJ Barker
#
# Dungeons and Dragons Web interface for 5E-Database python project
# This project adds a character builder web interface on top of the 5E-Database

import json
import os
import random
import tempfile
from bson import ObjectId

from flask import Flask, render_template, request, send_file, redirect, url_for, flash, jsonify
from pymongo import MongoClient
from pypdf import PdfReader, PdfWriter
from pypdf.generic import BooleanObject, NameObject

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "changeme-in-production")

# Configure Database - read URI from environment variable
MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
client = MongoClient(MONGODB_URI)
db = client["5e-database"]

# Define Database tables to use
RACES_TABLE         = "2014-races"
SKILLS_TABLE        = "2014-skills"
CLASSES_TABLE       = "2014-classes"
PROFICIENCIES_TABLE = "2014-proficiencies"
BACKGROUNDS_TABLE   = "2024-backgrounds"
ALIGNMENTS_TABLE    = "2024-alignments"
SUBCLASSES_TABLE    = "2024-subclasses"
CHARACTERS_TABLE    = "characters"   # saved player characters

standard_abilities = {
    "Barbarian": {"STR": 15, "DEX": 13, "CON": 14, "INT": 10, "WIS": 12, "CHA": 8},
    "Bard":      {"STR": 8,  "DEX": 14, "CON": 12, "INT": 13, "WIS": 10, "CHA": 15},
    "Cleric":    {"STR": 14, "DEX": 8,  "CON": 13, "INT": 10, "WIS": 15, "CHA": 12},
    "Druid":     {"STR": 8,  "DEX": 12, "CON": 14, "INT": 13, "WIS": 15, "CHA": 10},
    "Fighter":   {"STR": 15, "DEX": 14, "CON": 13, "INT": 8,  "WIS": 10, "CHA": 12},
    "Monk":      {"STR": 12, "DEX": 15, "CON": 13, "INT": 10, "WIS": 14, "CHA": 8},
    "Paladin":   {"STR": 15, "DEX": 10, "CON": 13, "INT": 8,  "WIS": 12, "CHA": 10},
    "Ranger":    {"STR": 12, "DEX": 15, "CON": 13, "INT": 8,  "WIS": 14, "CHA": 10},
    "Rogue":     {"STR": 12, "DEX": 15, "CON": 13, "INT": 14, "WIS": 10, "CHA": 8},
    "Sorcerer":  {"STR": 10, "DEX": 13, "CON": 14, "INT": 8,  "WIS": 12, "CHA": 15},
    "Warlock":   {"STR": 8,  "DEX": 14, "CON": 13, "INT": 12, "WIS": 10, "CHA": 15},
    "Wizard":    {"STR": 8,  "DEX": 12, "CON": 13, "INT": 15, "WIS": 14, "CHA": 10}
}

ABILITY_KEYS = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]

SPELLCASTING_ABILITY = {
    "Bard":     "CHA",
    "Cleric":   "WIS",
    "Druid":    "WIS",
    "Paladin":  "CHA",
    "Ranger":   "WIS",
    "Sorcerer": "CHA",
    "Warlock":  "CHA",
    "Wizard":   "INT",
}

CLASS_HIT_DIE = {
    "Barbarian": 12,
    "Bard":       8,
    "Cleric":     8,
    "Druid":      8,
    "Fighter":   10,
    "Monk":       8,
    "Paladin":   10,
    "Ranger":    10,
    "Rogue":      8,
    "Sorcerer":   6,
    "Warlock":    8,
    "Wizard":     6,
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def roll_ability_score():
    rolls = sorted([random.randint(1, 6) for _ in range(4)])
    return sum(rolls[1:])


def to_signed(num):
    return f"+{num}" if num > 0 else str(num)


def get_ability_modifier(ability):
    try:
        return (int(ability) - 10) // 2
    except (TypeError, ValueError):
        return 0


def get_ability_modifier_str(ability):
    try:
        return to_signed(get_ability_modifier(ability))
    except Exception:
        return ""


def get_proficiency_bonus(lvl):
    try:
        lvl = int(lvl)
    except (TypeError, ValueError):
        return 2
    return (lvl - 1) // 4 + 2


def get_all_skills():
    try:
        return {c["name"]: c["ability_score"]["name"] for c in db[SKILLS_TABLE].find({}, {"_id": 0})}
    except Exception:
        return {}


def get_selected_race_obj(race):
    try:
        return db[RACES_TABLE].find_one({"name": race}, {"_id": 0})
    except Exception:
        return None


def get_class_obj(class_name):
    try:
        return db[CLASSES_TABLE].find_one({"name": class_name}, {"_id": 0})
    except Exception:
        return None


def get_background_obj(background_name):
    try:
        return db[BACKGROUNDS_TABLE].find_one({"name": background_name}, {"_id": 0})
    except Exception:
        return None


def items_to_string(items):
    return ", ".join(str(i) for i in items)


def get_class_proficiency_options(class_name):
    try:
        class_obj = db[CLASSES_TABLE].find_one({"name": class_name}, {"_id": 0})
        if not class_obj or "proficiency_choices" not in class_obj:
            return [], 0
        choice_count = class_obj["proficiency_choices"][0]["choose"]
        choices_temp = class_obj["proficiency_choices"][0]["from"]["options"]
        choices = [t["item"]["name"].replace("Skill: ", "") for t in choices_temp]
        return choices, choice_count
    except Exception as e:
        app.logger.warning("Error extracting proficiencies for %s: %s", class_name, e)
        return [], 0


def validate_ability_score(value, default=10):
    try:
        return max(1, min(30, int(value)))
    except (TypeError, ValueError):
        return default


def validate_level(value):
    try:
        return max(1, min(20, int(value)))
    except (TypeError, ValueError):
        return 1


def sanitize_text(value, max_length=100, default="Unknown"):
    if not value:
        return default
    return str(value).strip()[:max_length]


def calc_max_hp(class_name, level, con_score):
    hit_die = CLASS_HIT_DIE.get(class_name, 8)
    con_mod = get_ability_modifier(con_score)
    hp = hit_die + con_mod
    hp += ((hit_die // 2 + 1) + con_mod) * (level - 1)
    return max(1, hp)


def get_saving_throws(class_name, abilities, prof_bonus):
    try:
        class_obj = get_class_obj(class_name)
        prof_saves = {st["name"] for st in class_obj.get("saving_throws", [])} if class_obj else set()
    except Exception:
        prof_saves = set()
    return {
        key: to_signed(get_ability_modifier(abilities[key]) + (prof_bonus if key in prof_saves else 0))
        for key in ABILITY_KEYS
    }


def get_weapon_proficiencies(class_name, race_name):
    try:
        profs = [c["name"] for c in db[PROFICIENCIES_TABLE].find(
            {"type": "Weapons", "$or": [{"classes.name": class_name}, {"races.name": race_name}]},
            {"_id": 0, "name": 1}
        )]
        return items_to_string(profs)
    except Exception:
        return ""


def get_tool_proficiencies(class_name, race_name):
    try:
        profs = [c["name"] for c in db[PROFICIENCIES_TABLE].find(
            {"type": "Artisan's Tools", "$or": [{"classes.name": class_name}, {"races.name": race_name}]},
            {"_id": 0, "name": 1}
        )]
        return items_to_string(profs)
    except Exception:
        return ""


def get_class_features_text(class_name, level):
    try:
        docs = list(db["2014-features"].find(
            {"class.name": class_name, "level": {"$lte": level}},
            {"_id": 0, "name": 1, "level": 1}
        ).sort("level", 1))
        if docs:
            return "\n".join(f"Lv{f['level']}: {f['name']}" for f in docs[:30])
        class_obj = get_class_obj(class_name)
        if class_obj and "features" in class_obj:
            return "\n".join(f["name"] for f in class_obj["features"][:30])
        return ""
    except Exception as e:
        app.logger.warning("Class features error for %s: %s", class_name, e)
        return ""


def get_new_features_at_level(class_name, level):
    try:
        docs = list(db["2014-features"].find(
            {"class.name": class_name, "level": level},
            {"_id": 0, "name": 1}
        ))
        return [f["name"] for f in docs]
    except Exception:
        return []


def get_spellcasting_fields(class_name, abilities, prof_bonus):
    spell_ability = SPELLCASTING_ABILITY.get(class_name)
    if not spell_ability:
        return "", "", ""
    mod = get_ability_modifier(abilities[spell_ability])
    return spell_ability, str(8 + prof_bonus + mod), to_signed(prof_bonus + mod)


def get_background_traits(background_name):
    try:
        bg = get_background_obj(background_name)
        if not bg:
            return ""
        parts = []
        if "feature" in bg:
            feat = bg["feature"]
            if feat.get("name"):
                parts.append(feat["name"])
            desc = feat.get("desc", [])
            parts.extend(desc[:2] if isinstance(desc, list) else [str(desc)[:300]])
        return "\n".join(parts)[:500]
    except Exception:
        return ""


def build_character_from_form():
    """Build a full character dict from the current POST form."""
    selected_race = sanitize_text(request.form.get("race"), default="")
    all_skills = get_all_skills()
    selected_race_obj = get_selected_race_obj(selected_race)
    lvl = validate_level(request.form.get("LVL"))
    prof_bonus = get_proficiency_bonus(lvl)
    selected_class = sanitize_text(request.form.get("class"), default="")
    selected_background = sanitize_text(request.form.get("background"), default="")

    abilities = {key: validate_ability_score(request.form.get(key)) for key in ABILITY_KEYS}
    modifiers = {key: get_ability_modifier_str(abilities[key]) for key in ABILITY_KEYS}

    speed = selected_race_obj.get("speed", 30) if selected_race_obj else 30
    size  = selected_race_obj.get("size", "") if selected_race_obj else ""
    languages = [c["name"] for c in selected_race_obj.get("languages", [])] if selected_race_obj else []

    subclass = sanitize_text(request.form.get("subclass"), default="")
    if subclass.lower() == "none":
        subclass = ""

    dex_mod = get_ability_modifier(abilities["DEX"])
    wis_mod = get_ability_modifier(abilities["WIS"])
    hit_die = CLASS_HIT_DIE.get(selected_class, 8)
    saving_throws = get_saving_throws(selected_class, abilities, prof_bonus)
    spell_ability, spell_save_dc, spell_atk_bonus = get_spellcasting_fields(
        selected_class, abilities, prof_bonus
    )

    character = {
        "Name":           sanitize_text(request.form.get("CharacterName")),
        "PlayerName":     sanitize_text(request.form.get("PlayerName")),
        "Race":           selected_race,
        "Class":          selected_class,
        "Subclass":       subclass,
        "Background":     selected_background,
        "Level":          lvl,
        "ProficiencyBonus": to_signed(prof_bonus),
        "Abilities":      abilities,
        "Modifiers":      modifiers,
        "Alignment":      sanitize_text(request.form.get("alignment"), default=""),
        "Speed":          speed,
        "Size":           size,
        "Languages":      languages,
        "Initiative":     to_signed(dex_mod),
        "ArmorClass":     str(10 + dex_mod),
        "MaxHP":          str(calc_max_hp(selected_class, lvl, abilities["CON"])),
        "HitDice":        f"1d{hit_die}",
        "PassivePerception": str(10 + wis_mod),
        "SavingThrows":   saving_throws,
        "WeaponProficiencies": get_weapon_proficiencies(selected_class, selected_race),
        "ToolProficiencies":   get_tool_proficiencies(selected_class, selected_race),
        "ClassFeatures":       get_class_features_text(selected_class, lvl),
        "SpellcastingAbility": spell_ability,
        "SpellSaveDC":         spell_save_dc,
        "SpellAtkBonus":       spell_atk_bonus,
        "BackgroundTraits":    get_background_traits(selected_background),
    }

    selected_proficiencies = request.form.getlist("proficiencies")
    character["Skills"] = {}
    for skill_name, ability_abbr in all_skills.items():
        mod = get_ability_modifier(abilities[ability_abbr])
        if skill_name in selected_proficiencies:
            character["Skills"][skill_name] = to_signed(mod + prof_bonus)
        else:
            character["Skills"][skill_name] = to_signed(mod)

    return character


def recalculate_character(char):
    """Recalculate all derived stats after a level change."""
    lvl        = char["Level"]
    abilities  = char["Abilities"]
    class_name = char["Class"]
    race_name  = char["Race"]
    prof_bonus = get_proficiency_bonus(lvl)
    all_skills = get_all_skills()

    dex_mod = get_ability_modifier(abilities["DEX"])
    wis_mod = get_ability_modifier(abilities["WIS"])
    hit_die = CLASS_HIT_DIE.get(class_name, 8)
    spell_ability, spell_save_dc, spell_atk_bonus = get_spellcasting_fields(
        class_name, abilities, prof_bonus
    )

    char["ProficiencyBonus"]    = to_signed(prof_bonus)
    char["Modifiers"]           = {k: get_ability_modifier_str(abilities[k]) for k in ABILITY_KEYS}
    char["Initiative"]          = to_signed(dex_mod)
    char["ArmorClass"]          = str(10 + dex_mod)
    char["MaxHP"]               = str(calc_max_hp(class_name, lvl, abilities["CON"]))
    char["HitDice"]             = f"1d{hit_die}"
    char["PassivePerception"]   = str(10 + wis_mod)
    char["SavingThrows"]        = get_saving_throws(class_name, abilities, prof_bonus)
    char["WeaponProficiencies"] = get_weapon_proficiencies(class_name, race_name)
    char["ToolProficiencies"]   = get_tool_proficiencies(class_name, race_name)
    char["ClassFeatures"]       = get_class_features_text(class_name, lvl)
    char["SpellcastingAbility"] = spell_ability
    char["SpellSaveDC"]         = spell_save_dc
    char["SpellAtkBonus"]       = spell_atk_bonus

    # Re-derive skill proficiencies by comparing to un-proficient value
    old_prof = get_proficiency_bonus(lvl - 1)
    char["Skills"] = {}
    for skill_name, ability_abbr in all_skills.items():
        mod = get_ability_modifier(abilities[ability_abbr])
        old_val = char.get("Skills", {}).get(skill_name, "")
        had_prof = old_val == to_signed(mod + old_prof)
        if had_prof:
            char["Skills"][skill_name] = to_signed(mod + prof_bonus)
        else:
            char["Skills"][skill_name] = to_signed(mod)

    return char


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def home_page():
    return render_template("home.html")


@app.route("/builder", methods=["GET", "POST"])
def character_builder():
    try:
        races       = sorted([r["name"] for r in db[RACES_TABLE].find({}, {"_id": 0, "name": 1})])
        classes     = sorted([c["name"] for c in db[CLASSES_TABLE].find({}, {"_id": 0, "name": 1})])
        backgrounds = sorted([b["name"] for b in db[BACKGROUNDS_TABLE].find({}, {"_id": 0, "name": 1})])
        alignments  = sorted([b["name"] for b in db[ALIGNMENTS_TABLE].find({}, {"_id": 0, "name": 1})])
    except Exception as e:
        app.logger.error("Database error loading options: %s", e)
        return "Database unavailable. Please try again later.", 503

    character      = None
    character_json = None
    abilities      = {key: 10 for key in ABILITY_KEYS}
    lvl            = 1
    character_name = "Unknown"
    player_name    = "Unknown"
    selected_race       = races[0] if races else ""
    selected_class      = classes[0] if classes else ""
    selected_background = backgrounds[0] if backgrounds else ""
    selected_alignment  = alignments[0] if alignments else ""
    selected_subclass   = ""
    selected_profs      = []

    subclasses = ["None"] + [
        c["name"] for c in db[SUBCLASSES_TABLE].find({"class.name": selected_class}, {"_id": 0, "name": 1})
    ]
    prof_choices, prof_choice_count = get_class_proficiency_options(selected_class)

    if request.method == "POST":
        character       = build_character_from_form()
        abilities       = character["Abilities"]
        lvl             = character["Level"]
        character_name  = character["Name"]
        player_name     = character["PlayerName"]
        selected_class  = character["Class"]
        selected_race   = character["Race"]
        selected_profs  = request.form.getlist("proficiencies")

        subclasses = ["None"] + [
            c["name"] for c in db[SUBCLASSES_TABLE].find({"class.name": selected_class}, {"_id": 0, "name": 1})
        ]
        prof_choices, prof_choice_count = get_class_proficiency_options(selected_class)

        if "Generate Abilities" in request.form:
            abilities = {key: roll_ability_score() for key in ABILITY_KEYS}
            character_json = json.dumps(character, indent=2)

        elif "Create Character" in request.form:
            character_json = json.dumps(character, indent=2)

        elif "Standard Abilities" in request.form:
            if selected_class in standard_abilities:
                abilities = standard_abilities[selected_class]

        elif "Save Character" in request.form:
            db[CHARACTERS_TABLE].insert_one(character)
            flash(f"{character['Name']} has been saved to your party!", "success")
            return redirect(url_for("characters_list"))

        elif "Save PDF" in request.form:
            template = "/res/DnD_2024_Character-Sheet R3.pdf"
            try:
                reader = PdfReader(template)
                writer = PdfWriter()
                writer.append_pages_from_reader(reader)
                writer._root_object[NameObject("/AcroForm")] = reader.trailer["/Root"]["/AcroForm"]
                writer._root_object["/AcroForm"][NameObject("/NeedAppearances")] = BooleanObject(True)

                name_field = character["Name"]
                if character["PlayerName"] not in ("Unknown", "", None):
                    name_field = f"{name_field} ({character['PlayerName']})"

                field_data = {
                    "CharacterName_Field": name_field,
                    "Race_Field":          character["Race"],
                    "Class_Field":         character["Class"],
                    "Subclass_Field":      character["Subclass"],
                    "Background_Field":    character["Background"],
                    "Alignment_Field":     character["Alignment"],
                    "LVL_Field":           str(character["Level"]),
                    "XP_Field":            "0",
                    "STR_Field":     str(character["Abilities"]["STR"]),
                    "DEX_Field":     str(character["Abilities"]["DEX"]),
                    "CON_Field":     str(character["Abilities"]["CON"]),
                    "INT_Field":     str(character["Abilities"]["INT"]),
                    "WIS_Field":     str(character["Abilities"]["WIS"]),
                    "CHA_Field":     str(character["Abilities"]["CHA"]),
                    "STR_Mod_Field": character["Modifiers"]["STR"],
                    "DEX_Mod_Field": character["Modifiers"]["DEX"],
                    "CON_Mod_Field": character["Modifiers"]["CON"],
                    "INT_Mod_Field": character["Modifiers"]["INT"],
                    "WIS_Mod_Field": character["Modifiers"]["WIS"],
                    "CHA_Mod_Field": character["Modifiers"]["CHA"],
                    "ProficiencyBonus":        character["ProficiencyBonus"],
                    "Initiative_Field":        character["Initiative"],
                    "ArmorClass_Field":        character["ArmorClass"],
                    "Speed_Field":             str(character["Speed"]),
                    "Size_Field":              character["Size"],
                    "HP_MAX_Field":            character["MaxHP"],
                    "HP_Current_Field":        character["MaxHP"],
                    "HitDice_Field":           character["HitDice"],
                    "PassivePerception_Field": character["PassivePerception"],
                    "STR_ST_Field": character["SavingThrows"]["STR"],
                    "DEX_ST_Field": character["SavingThrows"]["DEX"],
                    "CON_ST_Field": character["SavingThrows"]["CON"],
                    "INT_ST_Field": character["SavingThrows"]["INT"],
                    "WIS_ST_Field": character["SavingThrows"]["WIS"],
                    "CHA_ST_Field": character["SavingThrows"]["CHA"],
                    "Athletics_Field":      character["Skills"]["Athletics"],
                    "Acrobatics_Field":     character["Skills"]["Acrobatics"],
                    "SleightOfHand_Field":  character["Skills"]["Sleight of Hand"],
                    "Stealth_Field":        character["Skills"]["Stealth"],
                    "Arcana_Field":         character["Skills"]["Arcana"],
                    "History_Field":        character["Skills"]["History"],
                    "Investigation_Field":  character["Skills"]["Investigation"],
                    "Nature_Field":         character["Skills"]["Nature"],
                    "Religion_Field":       character["Skills"]["Religion"],
                    "AnimalHandling_Field": character["Skills"]["Animal Handling"],
                    "Insight_Field":        character["Skills"]["Insight"],
                    "Medicine_Field":       character["Skills"]["Medicine"],
                    "Perception_Field":     character["Skills"]["Perception"],
                    "Survival_Field":       character["Skills"]["Survival"],
                    "Decption_Field":       character["Skills"]["Deception"],
                    "Intimidation_Field":   character["Skills"]["Intimidation"],
                    "Performance_Field":    character["Skills"]["Performance"],
                    "Persuasion_Field":     character["Skills"]["Persuasion"],
                    "Languages_Field":           items_to_string(character["Languages"]),
                    "WeaponProficiencies_Field": character["WeaponProficiencies"],
                    "ToolProficiencies_Field":   character["ToolProficiencies"],
                    "Class_Features_Field":      character["ClassFeatures"],
                    "Spellcasting_MOD": character["SpellcastingAbility"],
                    "SpellSave_DC":     character["SpellSaveDC"],
                    "Spell_ATK_Bonus":  character["SpellAtkBonus"],
                    "Traits_Field":     character["BackgroundTraits"],
                }

                for page in writer.pages:
                    writer.update_page_form_field_values(page, field_data)

                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp_path = tmp.name
                    writer.write(tmp)

                return send_file(tmp_path, as_attachment=True, download_name="character.pdf")

            except FileNotFoundError:
                app.logger.error("PDF template not found: %s", template)
                return "PDF template not found.", 500
            except Exception as e:
                app.logger.error("PDF generation error: %s", e)
                return "An error occurred generating the PDF.", 500

    return render_template(
        "index.html",
        races=races,
        selected_race=selected_race,
        classes=classes,
        selected_class=selected_class,
        subclasses=subclasses,
        selected_subclass=selected_subclass,
        backgrounds=backgrounds,
        selected_background=selected_background,
        alignments=alignments,
        selected_alignment=selected_alignment,
        PlayerName=player_name,
        proficiency_choices=prof_choices,
        proficiency_count=prof_choice_count,
        selected_profs=selected_profs,
        CharacterName=character_name,
        LVL=lvl,
        STR=abilities["STR"],
        DEX=abilities["DEX"],
        CON=abilities["CON"],
        INT=abilities["INT"],
        WIS=abilities["WIS"],
        CHA=abilities["CHA"],
        character_json=character_json,
    )


@app.route("/characters")
def characters_list():
    try:
        chars = list(db[CHARACTERS_TABLE].find({}))
        for c in chars:
            c["_id"] = str(c["_id"])
        return render_template("characters.html", characters=chars)
    except Exception as e:
        app.logger.error("Error loading characters: %s", e)
        flash("Error loading characters.", "error")
        return render_template("characters.html", characters=[])


@app.route("/characters/<char_id>")
def character_detail(char_id):
    try:
        char = db[CHARACTERS_TABLE].find_one({"_id": ObjectId(char_id)})
        if not char:
            flash("Character not found.", "error")
            return redirect(url_for("characters_list"))
        char["_id"] = str(char["_id"])
        return render_template("character_detail.html", char=char)
    except Exception as e:
        app.logger.error("Error loading character %s: %s", char_id, e)
        flash("Error loading character.", "error")
        return redirect(url_for("characters_list"))


@app.route("/characters/<char_id>/levelup", methods=["GET", "POST"])
def character_levelup(char_id):
    try:
        char = db[CHARACTERS_TABLE].find_one({"_id": ObjectId(char_id)})
        if not char:
            flash("Character not found.", "error")
            return redirect(url_for("characters_list"))

        char["_id"] = str(char["_id"])

        if char["Level"] >= 20:
            flash(f"{char['Name']} is already at the maximum level (20).", "info")
            return redirect(url_for("character_detail", char_id=char_id))

        new_level  = char["Level"] + 1
        new_prof   = get_proficiency_bonus(new_level)
        hit_die    = CLASS_HIT_DIE.get(char["Class"], 8)
        con_mod    = get_ability_modifier(char["Abilities"]["CON"])
        hp_gained  = (hit_die // 2 + 1) + con_mod
        new_max_hp = calc_max_hp(char["Class"], new_level, char["Abilities"]["CON"])

        changes = [
            {"label": "Level",             "old": char["Level"],            "new": new_level},
            {"label": "Proficiency Bonus", "old": char["ProficiencyBonus"], "new": to_signed(new_prof)},
            {"label": "Max HP",            "old": char["MaxHP"],            "new": str(new_max_hp)},
        ]

        spell_ability = SPELLCASTING_ABILITY.get(char["Class"])
        if spell_ability:
            mod = get_ability_modifier(char["Abilities"][spell_ability])
            new_dc  = str(8 + new_prof + mod)
            new_atk = to_signed(new_prof + mod)
            if char.get("SpellSaveDC") != new_dc:
                changes.append({"label": "Spell Save DC",   "old": char.get("SpellSaveDC",""),   "new": new_dc})
            if char.get("SpellAtkBonus") != new_atk:
                changes.append({"label": "Spell Atk Bonus", "old": char.get("SpellAtkBonus",""), "new": new_atk})

        new_features = get_new_features_at_level(char["Class"], new_level)

        if request.method == "POST":
            char["Level"] = new_level
            updated = recalculate_character(char)
            doc_id  = updated.pop("_id")
            db[CHARACTERS_TABLE].replace_one({"_id": ObjectId(doc_id)}, updated)
            flash(f"{char['Name']} is now level {new_level}! 🎉", "success")
            return redirect(url_for("character_detail", char_id=char_id))

        return render_template(
            "levelup.html",
            char=char,
            new_level=new_level,
            changes=changes,
            hp_gained=hp_gained,
            new_max_hp=new_max_hp,
            con_mod=to_signed(con_mod),
            new_features=new_features,
        )

    except Exception as e:
        app.logger.error("Level up error for %s: %s", char_id, e)
        flash("An error occurred during level up.", "error")
        return redirect(url_for("characters_list"))


@app.route("/characters/<char_id>/delete", methods=["POST"])
def character_delete(char_id):
    try:
        result = db[CHARACTERS_TABLE].delete_one({"_id": ObjectId(char_id)})
        return jsonify({"ok": result.deleted_count == 1})
    except Exception as e:
        app.logger.error("Delete error for %s: %s", char_id, e)
        return jsonify({"ok": False}), 500


@app.route("/dice")
def dice_roller():
    return render_template("dice.html")


if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=5000, debug=debug_mode)
