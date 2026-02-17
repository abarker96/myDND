# AJ Barker
#
# Dungeons and Dragons Web interface for 5E-Database python project
# This project adds a character builder web interface on top of the 5E-Database

from flask import Flask, render_template_string, render_template, request, send_file
from pymongo import MongoClient
import json, random, tempfile
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, BooleanObject

app = Flask(__name__)

# Configure Database
client = MongoClient("mongodb://localhost:27017")
db = client["5e-database"]

# Define Database tables to use
RACES_TABLE = "2014-races"
SKILLS_TABLE = "2014-skills"
CLASSES_TABLE = "2014-classes"
PROFICIENCIES_TABLE = "2014-proficiencies"
BACKGROUNDS_TABLE = "2024-backgrounds"
ALIGNMENTS_TABLE = "2024-alignments"
SUBCLASSES_TABLE = "2024-subclasses"



standard_abilities = {
	"Barbarian":    {"STR": 15, "DEX": 13, "CON": 14, "INT": 10, "WIS": 12, "CHA": 8},
	"Bard":         {"STR": 8,  "DEX": 14, "CON": 12, "INT": 13, "WIS": 10, "CHA": 15},
	"Cleric":       {"STR": 14, "DEX": 8,  "CON": 13, "INT": 10, "WIS": 15, "CHA": 12},
	"Druid":        {"STR": 8,  "DEX": 12, "CON": 14, "INT": 13, "WIS": 15, "CHA": 10},
	"Fighter":      {"STR": 15, "DEX": 14, "CON": 13, "INT": 8,  "WIS": 10, "CHA": 12},
	"Monk":         {"STR": 12, "DEX": 15, "CON": 13, "INT": 10, "WIS": 14, "CHA": 8},
	"Paladin":      {"STR": 15, "DEX": 10, "CON": 13, "INT": 8,  "WIS": 12, "CHA": 10},
	"Ranger":       {"STR": 12, "DEX": 15, "CON": 13, "INT": 8,  "WIS": 14, "CHA": 10},
	"Rogue":        {"STR": 12, "DEX": 15, "CON": 13, "INT": 14, "WIS": 10, "CHA": 8},
	"Sorcerer":     {"STR": 10, "DEX": 13, "CON": 14, "INT": 8,  "WIS": 12, "CHA": 15},
	"Warlock":      {"STR": 8,  "DEX": 14, "CON": 13, "INT": 12, "WIS": 10, "CHA": 15},
	"Wizard":       {"STR": 8,  "DEX": 12, "CON": 13, "INT": 15, "WIS": 14, "CHA": 10}
}

def roll_ability_score():
	"""Generate random ability score based on D&D Rules
	Simulates rolling 4d6 and taking top 3
	:return: sum of top 3 of 4 random integers from 1-6
	"""
	rolls = sorted([random.randint(1,6) for _ in range(4)])
	return sum(rolls[1:])

def get_skill_score(character):
	"""
	Generate random ability score based on D&D Rules
	
	Currently this doesn't do anything.
	Need to finish building out functionality.
	
	From the handbook:
	Skills. For skills you have proficiency in, add your
	Proficiency Bonus to the ability modifier associated with
	that skill, and note the total. You might also wish to note
	the modifier for skills you're not proficient in, which is
	just the relevant ability modifier.
	
	Skill Modifier = Relevant Ability Modifier + Proficiency Bonus + Other Modifiers
	
	:param character:
	:return:
	"""
	proficiencyBonus = get_proficiency_bonus(character["Level"])
	selected_race = character["Race"]
	selected_class = character["Class"]
	race_proficiencies = [c["name"] for c in db[PROFICIENCIES_TABLE].find({"races.name": selected_race}, {"_id": 0, "name": 1})]
	class_proficiencies = [c["name"] for c in db[PROFICIENCIES_TABLE].find({"classes.name": selected_class}, {"_id": 0, "name": 1})]
	proficiencies = { }
	for c in race_proficiencies:
		proficiencies[c] = proficiencyBonus

def get_class_proficiency_options(class_name):
	"""
	Get class proficiency options from database based on class name
	:param class_name:
	:return:
	"""
	class_obj = db[CLASSES_TABLE].find_one(
		{"name": class_name},
		{"_id": 0}
	)

	if not class_obj:
		print("No class found:", class_name)
		return [], 0

	if "proficiency_choices" not in class_obj:
		print("No proficiency_choices in class:", class_name)
		return [], 0

	try:
		choice_count = class_obj["proficiency_choices"][0]["choose"]
		choices_temp = class_obj["proficiency_choices"][0]["from"]["options"]

		choices = [
			t["item"]["name"].replace("Skill: ", "")
			for t in choices_temp
		]

		return choices, choice_count

	except Exception as e:
		print("Error extracting proficiencies:", e)
		return [], 0

def to_signed(num):
	"""
	Input integer and return formatted string representation
	:param num: Integer value
	:return: Formatted string of number
	"""
	if num > 0:
		return "+" + str(num)
	else:
		return str(num)

def get_ability_modifier_str(ability):
	"""
	Calculate ability modifier and return it as a string
	:param ability: Integer value of ability
	:return: Formatted string of ability modifier
	"""
	try:
		ability = int(ability)
	except:
		return ""
	mod = (ability - 10) // 2
	if mod <= 0:
		ret = str(mod)
	else:
		ret = "+" + str(mod)
	return ret

def get_proficiency_bonus(lvl):
	"""
	Input Level, return proficiency bonus calculated based on level
	:param lvl: character level
	:return: return proficiency bonus
	"""
	try:
		lvl = int(lvl)
	except:
		return 1
	return (lvl - 1) // 4 + 2

def get_all_skills():
	"""
	Get all skills from database
	:return: Return all skill names from database
	"""
	skills = {c["name"]: c["ability_score"]["name"] for c in db[SKILLS_TABLE].find({}, {"_id": 0})}
	return skills

def get_selected_races_obj(race):
	"""
	Get database information for selected race
	:param race: Character Race
	:return: Table Object for selected race
	"""
	race = db[RACES_TABLE].find({"name":race}, {"_id": 0})
	try:
		race = race[0]
	except Exception as e:
		return None
	return race

def list_to_string(list):
	"""
	Input a list of values and return formatted string
	:param list: list of values to format
	:return: Cama separated string value
	"""
	txt = str(list).replace("[", "").replace("]", "").replace("'","")
	return txt

def get_character():
	"""
	Get Character data from form
	:return: Returns formated character dict
	"""
	selected_race = request.form.get("race")
	all_skills = get_all_skills()
	selected_race_obj = get_selected_races_obj(selected_race)
	lvl = request.form.get("LVL") or 1
	character = {
				"Name": request.form.get("CharacterName") or "Unknown",
				"PlayerName": request.form.get("PlayerName") or "Unknown",
				"Race": selected_race,
				"Class": request.form.get("class"),
				"Subclass": request.form.get("subclass"),
				"Background": request.form.get("background"),
				"Level": lvl,
				"ProficiencyBonus": "+" + str(get_proficiency_bonus(lvl)),
				"Abilities": {
					"STR": request.form.get("STR"),
					"DEX": request.form.get("DEX"),
					"CON": request.form.get("CON"),
					"INT": request.form.get("INT"),
					"WIS": request.form.get("WIS"),
					"CHA": request.form.get("CHA"),
				},
				"Modifiers": {
					"STR": get_ability_modifier_str(request.form.get("STR")),
					"DEX": get_ability_modifier_str(request.form.get("DEX")),
					"CON": get_ability_modifier_str(request.form.get("CON")),
					"INT": get_ability_modifier_str(request.form.get("INT")),
					"WIS": get_ability_modifier_str(request.form.get("WIS")),
					"CHA": get_ability_modifier_str(request.form.get("CHA"))
				},
				"Alignment": request.form.get("alignment"),
				"Speed": selected_race_obj["speed"],
				"Languages": [c["name"] for c in selected_race_obj["languages"]]
			}
	
	# define skills
	selected_proficiencies = request.form.getlist("proficiencies")
	character["Skills"] = {}
	for s in all_skills:
		ability = all_skills[s]
		if s in selected_proficiencies:
			character["Skills"][s] = to_signed(int(character["Modifiers"][ability]) + int(character["ProficiencyBonus"]))
		else:
			character["Skills"][s] = to_signed(int(character["Modifiers"][ability]))
	
	# check for empty subclass
	if character["Subclass"] == "None":
		character["Subclass"] = ""
	
	return character

@app.route("/", methods=["GET", "POST"])
def home():
	"""
	Main program for web app
	:return:
	"""
	# Get options from DB
	races = sorted([r["name"] for r in db[RACES_TABLE].find({}, {"_id": 0, "name": 1})])
	classes = sorted([c["name"] for c in db[CLASSES_TABLE].find({}, {"_id": 0, "name": 1})])
	backgrounds = sorted([b["name"] for b in db[BACKGROUNDS_TABLE].find({}, {"_id": 0, "name": 1})])
	alignments = sorted([b["name"] for b in db[ALIGNMENTS_TABLE].find({}, {"_id": 0, "name": 1})])
	
	# Initialize empty character
	character = None
	abilities = {
		"STR": 3,
		"DEX": 3,
		"CON": 3,
		"INT": 3,
		"WIS": 3,
		"CHA": 3
	}
	lvl = 1
	characterName = "Unknown"
	playerName = "Unknown"

	selected_race=races[0]
	selected_class=classes[0]
	selected_background=backgrounds[0]
	selected_alignment=alignments[0]
	selected_subclass=""
	subclasses = ["None"] + [c["name"] for c in db[SUBCLASSES_TABLE].find({"class.name": selected_class}, {"_id": 0, "name": 1})]
	prof_choices, prof_choice_count = get_class_proficiency_options(selected_class)
	selected_profs = []

	# Get user selection
	if request.method == "POST":
		#get data from character
		character = get_character()
		abilities = character["Abilities"]
		lvl = character["Level"]
		characterName = character["Name"]
		playerName = character["PlayerName"]
		selected_class = character["Class"]
		selected_race = character["Race"]
		
		# Get data from form
		subclasses = ["None"] + [c["name"] for c in db[SUBCLASSES_TABLE].find({"class.name":selected_class}, {"_id": 0, "name": 1})]
		prof_choices, prof_choice_count = get_class_proficiency_options(selected_class)
		selected_profs = request.form.getlist("proficiencies")
		
		
		if "Generate Abilities" in request.form: # Generate Random Abilities button was pressed
			abilities = {
				"STR": roll_ability_score(),
				"DEX": roll_ability_score(),
				"CON": roll_ability_score(),
				"INT": roll_ability_score(),
				"WIS": roll_ability_score(),
				"CHA": roll_ability_score()
				}
			character = json.dumps(character, indent=2)
		if "Create Character" in request.form: # Create Character button was pressed
			character = json.dumps(character, indent=2)
		
		if "Standard Abilities" in request.form:
			if selected_class in standard_abilities:
				abilities = standard_abilities[selected_class]
			
		if "Save PDF" in request.form: # Save PDF button was pressed
			# Configure PDF
			template = "/res/DnD_2024_Character-Sheet R3.pdf"
			reader = PdfReader(template)
			writer = PdfWriter()
			writer.append_pages_from_reader(reader)
			
			writer._root_object[NameObject("/AcroForm")] = reader.trailer["/Root"]["/AcroForm"]
			writer._root_object["/AcroForm"][NameObject("/NeedAppearances")] = BooleanObject(True)
			
			name_field = character["Name"]
			if character["PlayerName"] != "Unknown" and character["PlayerName"] is not None:
				name_field = name_field + " (" + character["PlayerName"] + ")"
			
			# Configure data for inserting into PDF
			field_data = {
				"CharacterName_Field": name_field,
				"Race_Field": character["Race"],
				"Class_Field": character['Class'],
				"Subclass_Field": character['Subclass'],
				"Background_Field": character["Background"],
				"Alignment_Field": character["Alignment"],
				
				"STR_Field": str(character["Abilities"]["STR"]),
				"DEX_Field": str(character["Abilities"]["DEX"]),
				"CON_Field": str(character["Abilities"]["CON"]),
				"INT_Field": str(character["Abilities"]["INT"]),
				"WIS_Field": str(character["Abilities"]["WIS"]),
				"CHA_Field": str(character["Abilities"]["CHA"]),
				
				"STR_Mod_Field": character["Modifiers"]["STR"],
				"DEX_Mod_Field": character["Modifiers"]["DEX"],
				"CON_Mod_Field": character["Modifiers"]["CON"],
				"INT_Mod_Field": character["Modifiers"]["INT"],
				"WIS_Mod_Field": character["Modifiers"]["WIS"],
				"CHA_Mod_Field": character["Modifiers"]["CHA"],
				
				"LVL_Field": str(character["Level"]),
				"ProficiencyBonus": character["ProficiencyBonus"],
				
				#"Traits_Field": str(character["Trait"]),
				# "Languages_Field": ", ".join(character["Languages"]),
				"Languages_Field": list_to_string(character["Languages"]),
				
				#STR
				"Athletics_Field": character["Skills"]["Athletics"],
				#DEX
				"Acrobatics_Field": character["Skills"]["Acrobatics"],
				"SleightOfHand_Field": character["Skills"]["Sleight of Hand"],
				"Stealth_Field": character["Skills"]["Stealth"],
				#INT
				"Arcana_Field": character["Skills"]["Arcana"],
				"History_Field": character["Skills"]["History"],
				"Investigation_Field": character["Skills"]["Investigation"],
				"Nature_Field": character["Skills"]["Nature"],
				"Religion_Field": character["Skills"]["Religion"],
				#WIS
				"AnimalHandling_Field": character["Skills"]["Animal Handling"],
				"Insight_Field": character["Skills"]["Insight"],
				"Medicine_Field": character["Skills"]["Medicine"],
				"Perception_Field": character["Skills"]["Perception"],
				"Survival_Field": character["Skills"]["Survival"],
				#CHA
				"Decption_Field": character["Skills"]["Deception"],
				"Intimidation_Field": character["Skills"]["Intimidation"],
				"Performance_Field": character["Skills"]["Performance"],
				"Persuasion_Field": character["Skills"]["Persuasion"],
				
				"Speed_Field": character["Speed"]
			}
			
			# update all pages in pdf
			for page in writer.pages:
				writer.update_page_form_field_values(page, field_data)
			
			tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
			with open(tmp.name, "wb") as f:
				writer.write(f)
			
			# export pdf
			return send_file(tmp.name, as_attachment=True, download_name="character.pdf")
		
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
		PlayerName=playerName,
	    proficiency_choices=prof_choices,
	    proficiency_count=prof_choice_count,
	    selected_profs=selected_profs,
		CharacterName=characterName,
		LVL=lvl,
		STR=abilities["STR"],
		DEX=abilities["DEX"],
		CON=abilities["CON"],
		INT=abilities["INT"],
		WIS=abilities["WIS"],
		CHA=abilities["CHA"]
	)

# Run the app
if __name__ == "__main__":
	app.run(host="0.0.0.0", port=5000)
