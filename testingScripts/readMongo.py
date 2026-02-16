from pymongo import MongoClient
import json


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

def to_signed(num):
	if num > 0:
		return "+" + str(num)
	else:
		return str(num)

character = {
				"Name": "Unknown",
				"PlayerName": "Unknown",
				"Race": "Elf",
				"Class": "Wizard",
				"Subclass": "",
				"Background": "Acolyte",
				"Level": 1,
				"ProficiencyBonus": "+2",
				"Abilities": {
					"STR": 8,
					"DEX": 9,
					"CON": 10,
					"INT": 16,
					"WIS": 17,
					"CHA": 13,
				},
				"Modifiers": {
					"STR_MOD": get_ability_modifier_str(8),
					"DEX_MOD": get_ability_modifier_str(9),
					"CON_MOD": get_ability_modifier_str(10),
					"INT_MOD": get_ability_modifier_str(16),
					"WIS_MOD": get_ability_modifier_str(17),
					"CHA_MOD": get_ability_modifier_str(13)
				},
				"Skills": {},
				"Alignment": "Chaotic Good"
			}

def print_all_class_proficiencies():
	classes = db["2014-classes"].find({}, {"_id": 0})
	for c in classes:
		print(f"{c["name"]}, choose ({c["proficiency_choices"][0]["choose"]})")
		for v in c["proficiency_choices"][0]["from"]["options"]:
			print(v["item"]["name"].replace("Skill: ", "\t"))

def get_class_proficiency_options(class_name):
	class_obj = db["2014-classes"].find_one(
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
	
def get_all_skills():
	skills = {c["name"]:c["ability_score"]["name"] for c in db["2014-skills"].find({}, {"_id": 0})}
	return skills
	

client = MongoClient("mongodb://localhost:27017")
db = client["5e-database"]

#classes = sorted([c["name"] for c in db["2014-classes"].find({}, {"_id": 0, "name": 1})])

selected_class = "Wizard"
#classes = sorted([c for c in db["2014-subclasses"].find({}, {"_id": 0, "name": 1})])
subclasses = [c["name"] for c in db["2014-subclasses"].find({"class.name":selected_class}, {"_id": 0})]

#print_all_class_proficiencies()

"""
choices,count = get_class_proficiency_options(selected_class)
print(f"Select {count}: ")
for c in choices:
	print(f"\t{c}")
"""
"""
skills = get_all_skills()
for c in skills:
	print(f"\t{c} : {skills[c]}")
"""

# define skills
selected_proficiencies = ["Arcana","Religion"]
all_skills = get_all_skills()
for s in all_skills:
	ability = all_skills[s] + "_MOD"
	if s in selected_proficiencies:
		character["Skills"][s] = to_signed(int(character["Modifiers"][ability]) + int(character["ProficiencyBonus"]))
	else:
		character["Skills"][s] = to_signed(int(character["Modifiers"][ability]))

for c in character:
	print(f"{c} : {character[c]}")
#print(character)

client.close()