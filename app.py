# AJ Barker
# Dungeons and Dragons Web interface for 5E-Database python project
# This project adds a character builder web interface on top of the 5E-Database
# More changes to come

from flask import Flask, render_template_string, request, send_file
from pymongo import MongoClient
import json, random, tempfile
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, BooleanObject

app = Flask(__name__)

client = MongoClient("mongodb://localhost:27017")
db = client["5e-database"]

TEMPLATE = """
<h1>D&D 5e Character Creator</h1>

<form method="POST">

  <label>Player Name:</label>
  <input type="text" id="PlayerName" name="PlayerName"value={{PlayerName}}>

	<br><br>

  <label>Character Name:</label>
  <input type="text" id="CharacterName" name="CharacterName"value={{CharacterName}}>

	<br><br>
	
  <label for="LVL">Level (1-12):</label>
  <input type="number" id="LVL" name="LVL" min="1" max="12" value={{LVL}} default=1>
	
	<br><br>
	
<label>Race:</label>
<select name="race">
{% for race in races %}
	<option value="{{ race }}"
		{% if selected_race == race %}selected{% endif %}>
		{{ race }}
	</option>
{% endfor %}
</select>
<br><br>

<label>Class:</label>
<select name="class" onchange="this.form.submit()">
{% for c in classes %}
	<option value="{{ c }}"
		{% if selected_class == c %}selected{% endif %}>
		{{ c }}
	</option>
{% endfor %}
</select>
<br><br>

<label>Subclass:</label>
<select name="subclass">
{% for c in subclasses %}
	<option value="{{ c }}"
		{% if selected_subclass == c %}selected{% endif %}>
		{{ c }}
	</option>
{% endfor %}
</select>
<br><br>

<label>Background:</label>
<select name="background">
{% for bg in backgrounds %}
	<option value="{{ bg }}"
		{% if selected_background == bg %}selected{% endif %}>
		{{ bg }}
	</option>
{% endfor %}
</select>
<br><br>

<label>Alignment:</label>
<select name="alignment">
{% for a in alignments %}
	<option value="{{ a }}"
		{% if selected_alignment == a %}selected{% endif %}>
		{{ a }}
	</option>
{% endfor %}
</select>
<br><br>

  <label for="STR">STR (3-18):</label>
  <input type="number" id="STR" name="STR" min="3" max="18" value={{STR}}>
  
  <label for="DEX">DEX (3-18):</label>
  <input type="number" id="DEX" name="DEX" min="3" max="18" value={{DEX}}>

	<br><br>

  <label for="CON">CON (3-18):</label>
  <input type="number" id="CON" name="CON" min="3" max="18" value={{CON}}>

  <label for="INT">INT (3-18):</label>
  <input type="number" id="INT" name="INT" min="3" max="18" value={{INT}}>

	<br><br>
	
  <label for="WIS">WIS (3-18):</label>
  <input type="number" id="WIS" name="WIS" min="3" max="18" value={{WIS}}>

  <label for="CHA">CHA (3-18):</label>
  <input type="number" id="CHA" name="CHA" min="3" max="18" value={{CHA}}>

	<br><br>
	<br><br>
	
<button method="/" name="Generate Abilities">Generate Random Abilities</button>
	<br><br>
<button method="/" name="Save PDF">Save PDF</button>
	<br><br>
</form>

{% if character %}
<h2>Character Summary</h2>
<pre>{{ character }}</pre>
{% endif %}
"""

def roll_ability_score():
	"""Generate random ability score based on D&D Rules"""
	rolls = sorted([random.randint(1,6) for _ in range(4)])
	return sum(rolls[1:])

def get_ability_modifier_str(ability):
	"""Calculate ability modifier and return it as a string"""
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
	"""Input Level, return proficiency bonus"""
	try:
		lvl = int(lvl)
	except:
		return 1
	return (lvl - 1) // 4 + 2

def get_character():
	character = {
				"Name": request.form["CharacterName"] or "Unknown",
				"PlayerName": request.form["PlayerName"] or "Unknown",
				"Race": request.form["race"],
				"Class": request.form["class"],
				#"Subclass": request.form["subclass"],
				"Background": request.form["background"],
				"Level": request.form["LVL"] or 1,
				"Abilities": {
					"STR": request.form["STR"],
					"DEX": request.form["DEX"],
					"CON": request.form["CON"],
					"INT": request.form["INT"],
					"WIS": request.form["WIS"],
					"CHA": request.form["CHA"],
				},
				"Modifiers": {
					"STR_MOD": get_ability_modifier_str(request.form["STR"]),
					"DEX_MOD": get_ability_modifier_str(request.form["DEX"]),
					"CON_MOD": get_ability_modifier_str(request.form["CON"]),
					"INT_MOD": get_ability_modifier_str(request.form["INT"]),
					"WIS_MOD": get_ability_modifier_str(request.form["WIS"]),
					"CHA_MOD": get_ability_modifier_str(request.form["CHA"])
				},
				"Alignment": request.form["alignment"]
			}
	return character

@app.route("/", methods=["GET", "POST"])
def home():
	# Get options from DB
	races = sorted([r["name"] for r in db["2014-races"].find({}, {"_id": 0, "name": 1})])
	classes = sorted([c["name"] for c in db["2014-classes"].find({}, {"_id": 0, "name": 1})])
	#subclasses = sorted([c["name"] for c in db["2014-subclasses"].find({}, {"_id": 0, "name": 1})])
	backgrounds = sorted([b["name"] for b in db["2024-backgrounds"].find({}, {"_id": 0, "name": 1})])
	alignments = sorted([b["name"] for b in db["2024-alignments"].find({}, {"_id": 0, "name": 1})])
	
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
	subclasses = [c["name"] for c in db["2014-subclasses"].find({"class.name": selected_class}, {"_id": 0, "name": 1})]

	# Get user selection
	if request.method == "POST":
		abilities = {
			"STR": request.form["STR"] or 3,
			"DEX": request.form["DEX"] or 3,
			"CON": request.form["CON"] or 3,
			"INT": request.form["INT"] or 3,
			"WIS": request.form["WIS"] or 3,
			"CHA": request.form["CHA"] or 3
		}
		lvl=request.form["LVL"] or 1
		characterName = request.form["CharacterName"] or "Unknown"
		playerName = request.form["PlayerName"] or "Unknown"
		selected_class = request.form["class"]
		subclasses = [c["name"] for c in db["2014-subclasses"].find({"class.name":selected_class}, {"_id": 0, "name": 1})]
		if "Generate Abilities" in request.form: # Generate Random Abilities button was pressed
			character = get_character()
			lvl = character["Level"]
			characterName = character["Name"]
			playerName = character["PlayerName"]
			abilities = {
				"STR": roll_ability_score(),
				"DEX": roll_ability_score(),
				"CON": roll_ability_score(),
				"INT": roll_ability_score(),
				"WIS": roll_ability_score(),
				"CHA": roll_ability_score()
				}
			selected_race=character["Race"]
			selected_class=character["Class"]
			selected_background=character["Background"]
			selected_alignment=character["Alignment"]
			#subclasses = [c["name"] for c in db["2014-subclasses"].find({"class.name":selected_class}, {"_id": 0})]
			character = json.dumps(character, indent=2)
		if "Create Character" in request.form: # Create Character button was pressed
			character = get_character()
			playerName = character["PlayerName"]
			characterName = character["Name"]
			lvl = character["Level"]
			abilities = character["Abilities"]
			selected_race=character["Race"]
			selected_class=character["Class"]
			selected_background=character["Background"]
			selected_alignment=character["Alignment"]
			#subclasses = [c["name"] for c in db["2014-subclasses"].find({"class.name":selected_class}, {"_id": 0})]
			character = json.dumps(character, indent=2)
		if "Save PDF" in request.form: # Save PDF button was pressed
			character = get_character()
			template = "/res/DnD_2024_Character-Sheet R3.pdf"
			reader = PdfReader(template)
			writer = PdfWriter()
			writer.append_pages_from_reader(reader)
			
			writer._root_object[NameObject("/AcroForm")] = reader.trailer["/Root"]["/AcroForm"]
			writer._root_object["/AcroForm"][NameObject("/NeedAppearances")] = BooleanObject(True)
			
			name_field = character["Name"]
			if character["PlayerName"] != "Unknown" and character["PlayerName"] is not None:
				name_field = name_field + " (" + character["PlayerName"] + ")"
			field_data = {
				"CharacterName_Field": name_field,
				"Race_Field": character["Race"],
				"Class_Field": character['Class'],
				#"Subclass_Field": character['Subclass'],
				"Background_Field": character["Background"],
				"Alignment_Field": character["Alignment"],
				
				"STR_Field": str(character["Abilities"]["STR"]),
				"DEX_Field": str(character["Abilities"]["DEX"]),
				"CON_Field": str(character["Abilities"]["CON"]),
				"INT_Field": str(character["Abilities"]["INT"]),
				"WIS_Field": str(character["Abilities"]["WIS"]),
				"CHA_Field": str(character["Abilities"]["CHA"]),
				
				"STR_Mod_Field": get_ability_modifier_str(character["Abilities"]["STR"]),
				"DEX_Mod_Field": get_ability_modifier_str(character["Abilities"]["DEX"]),
				"CON_Mod_Field": get_ability_modifier_str(character["Abilities"]["CON"]),
				"INT_Mod_Field": get_ability_modifier_str(character["Abilities"]["INT"]),
				"WIS_Mod_Field": get_ability_modifier_str(character["Abilities"]["WIS"]),
				"CHA_Mod_Field": get_ability_modifier_str(character["Abilities"]["CHA"]),
				
				"LVL_Field": str(character["Level"]),
				"ProficiencyBonus": "+" + str(get_proficiency_bonus(character["Level"])),
				
				#"Traits_Field": str(character["Trait"]),
				# "Languages_Field": ", ".join(character["Languages"]),
				"Languages_Field": "Common",
			}
			
			for page in writer.pages:
				writer.update_page_form_field_values(page, field_data)
		
			tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
			with open(tmp.name, "wb") as f:
				writer.write(f)

			selected_race=character["Race"]
			selected_class=character["Class"]
			selected_background=character["Background"]
			selected_alignment=character["Alignment"]
			#subclasses = [c["name"] for c in db["2014-subclasses"].find({"class.name":selected_class}, {"_id": 0})]
			character = json.dumps(character, indent=2)
			return send_file(tmp.name, as_attachment=True, download_name="character.pdf")
		
		# Return data
		return render_template_string(
			TEMPLATE,
			PlayerName=playerName,
			CharacterName=characterName,
			LVL=lvl,
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
			STR=abilities["STR"],
			DEX=abilities["DEX"],
			CON=abilities["CON"],
			INT=abilities["INT"],
			WIS=abilities["WIS"],
			CHA=abilities["CHA"]
		)
	return render_template_string(
		TEMPLATE,
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
		CharacterName=characterName,
		LVL=lvl,
		STR=abilities["STR"],
		DEX=abilities["DEX"],
		CON=abilities["CON"],
		INT=abilities["INT"],
		WIS=abilities["WIS"],
		CHA=abilities["CHA"]
	)

if __name__ == "__main__":
	app.run(host="0.0.0.0", port=5000)
