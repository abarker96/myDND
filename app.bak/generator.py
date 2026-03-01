# generator.py
import random

RACES = [
	"Human", "Elf", "Dwarf", "Halfling", "Dragonborn",
	"Gnome", "Goliath", "Half-Elf", "Half-Orc", "Orc", "Tiefling", "Asimar"
]

CLASSES = [
	"Fighter",
	"Wizard",
	"Rogue",
	"Cleric",
	"Barbarian",
	"Bard",
	"Paladin",
	"Ranger",
	"Sorcerer",
	"Warlock",
	"Monk",
	"Druid"
]

SUBCLASSES = {
	"Fighter": ["Champion", "Battle Master", "Eldritch Knight"],
	"Wizard": ["Evocation", "Illusion", "Necromancy", "Divination"],
	"Rogue": ["Thief", "Assassin", "Arcane Trickster"],
	"Cleric": ["Life", "Light", "War", "Trickery"],
	"Barbarian": ["Berserker", "Totem Warrior", "Wild Magic"],
	"Bard": ["Lore", "Valor", "Swords"],
	"Paladin": ["Devotion", "Vengeance", "Ancients"],
	"Ranger": ["Hunter", "Beast Master", "Gloom Stalker"],
	"Sorcerer": ["Draconic Bloodline", "Wild Magic"],
	"Warlock": ["Fiend", "Great Old One", "Archfey"],
	"Monk": ["Open Hand", "Shadow", "Four Elements"],
	"Druid": ["Land", "Moon", "Spores"]
}

ALIGNMENTS = [
	"Lawful Good", "Neutral Good", "Chaotic Good",
	"Lawful Neutral", "True Neutral", "Chaotic Neutral",
	"Lawful Evil", "Neutral Evil", "Chaotic Evil"
]

TRAITS = {
	"Human" : "Resourceful, Skillful, Versatile",
	"Elf" : "Darkvision, Elven Lineage, Fey Ancestry, Keen Senses,Â Trance",
	"Orc" : "Adrenaline Rush, Darkvision, Relentless Endurance",
	"Dwarf" : "Darkvision, Dwarven Resilience, Dwarven Toughness, Stonecunning",
	"Halfling" : "Brave, Halfling Nimbleness, Luck, Naturally Stealthy",
	"Dragonborn" : "Dragon Ancestry, Breath Weapon, Damage Resistance, Darkvision, Draconic Flight",
	"Gnome" : "Darkvision, Gnomish Cunning, Gnomish Lineage",
	"Goliath" : "Giant Ancestry, Large Form, Powerful Build",
	"Half-Elf" : "+2 Charisma, +1 to Two Other Ability Scores, Darkvision, Fey Ancestry, Skill Versatility",
	"Half-Orc" : "+2 Strength, +1 Constitution, Darkvision, Menacing, Relentless Endurance, Savage Attacks",
	"Tiefling" : "Darkvision, Fiendish Legacy, Otherworldly Presence",
	"Asimar" : "Celestial Resistance, Darkvision, Healing Hands, Light Bearer, Celestial Revelation"
}

BACKGROUNDS = [
	"Acolyte",
	"Criminal",
	"Sage",
	"Soldier",
	"Artisan",
	"Charlatan",
	"Entertainer",
	"Farmer",
	"Guard",
	"Guide",
	"Hermit",
	"Merchant",
	"Noble",
	"Sailor",
	"Scribe",
	"Wayfarer"
]


LANGUAGES = [
	"Common",
	"Common Sign Language",
	"Draconic",
	"Dwarvish",
	"Elvish",
	"Giant",
	"Gnomish",
	"Goblin",
	"Halfling",
	"Orc",
	"Abyssal",
	"Celestial",
	"Deep Speech",
	"Druidic",
	"Infernal",
	"Primordial",
	"Sylvan",
	"Thieves' Cant",
	"Undercommon"
]

RARE_LANGUAGES = [
	"Abyssal",
	"Celestial",
	"Deep Speech",
	"Druidic",
	"Infernal",
	"Primordial",
	"Sylvan",
	"Thieves' cant",
	"Undercommon"
]


ALL_LANGUAGES = LANGUAGES + RARE_LANGUAGES

def roll_ability_score():
	rolls = sorted([random.randint(1,6) for _ in range(4)])
	return sum(rolls[1:])

def generate_abilities():
	return {
		"STR": roll_ability_score(),
		"DEX": roll_ability_score(),
		"CON": roll_ability_score(),
		"INT": roll_ability_score(),
		"WIS": roll_ability_score(),
		"CHA": roll_ability_score()
	}

def generate_character(data):
	chosen_class = pick(data.get("class", "None"), CLASSES)
	chosen_race = pick(data.get("race", "None"), RACES)
	chosen_subclass = pick(data.get("subclass", "None"), SUBCLASSES[chosen_class])
	chosen_background = pick(data.get("background", "None"), BACKGROUNDS)
	chosen_alignment = pick(data.get("alignment", "None"), ALIGNMENTS)

	trait = None
	if chosen_race in TRAITS:
		trait = TRAITS[chosen_race]

	return {
		"Name": pick(data.get("name", "Unnamed Hero"), ["Unnamed Hero"]),
		#"Age": pick(data.get("age", "Unknown"), ["Unknown"]),
		"Race": pick(chosen_race, RACES),
		"Class": chosen_class,
		"Subclass": chosen_subclass,
	"Background": chosen_background,
		"Alignment": chosen_alignment,
		"Abilities": generate_abilities(),
	"Trait": trait,
	"Level": data.get("level", 1)
	}
	print(f"Level: ",data.get("level", "None"))

def get_ability_modifier_str(ability):
	"""Calculate ability modifier and return it as a string"""
	mod = (ability - 10) // 2
	if mod <= 0:
		ret = str(mod)
	else:
		ret = "+" + str(mod)
	return ret

def pick(selection, options):
	"""Return selection if not 'Random', else choose randomly from options"""
	if selection == "Random" or not selection:
			return random.choice(options)
	return selection

def get_proficiency_bonus(lvl):
	"""Input Level, return proficiency bonus"""
	try:
		lvl = int(lvl)
	except:
		return 1
	return (lvl - 1) // 4 + 2
