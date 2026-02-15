from flask import Flask, render_template, request, send_file
import json
from generator import *
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, BooleanObject
import tempfile
import os
import random

app = Flask(__name__)

@app.route("/generate", methods=["POST"])
def generate():
	character = generate_character(request.form)

	# Create temp PDF
	temp_dir = tempfile.gettempdir()
	pdf_path = os.path.join(temp_dir, "character.pdf")

	generate_pdf(character, pdf_path)  # your existing PDF function

	return render_template(
		"index.html",
		character=character,
	 )

@app.route("/preview")
def preview_pdf():
	temp_dir = tempfile.gettempdir()
	pdf_path = os.path.join(temp_dir, "character.pdf")

	return send_file(
		pdf_path,
		mimetype="application/pdf",
		as_attachment=False
	)

@app.route("/", methods=["GET", "POST"])
def index():
	character = None

	if request.method == "POST":
		data = {
			"name": request.form.get("name"),
			#"age": request.form.get("age"),
			"level": request.form.get("level"),
			"race": request.form.get("race"),
			"class": request.form.get("class"),
			"subclass": request.form.get("subclass"),
			"background": request.form.get("background"),
			"alignment": request.form.get("alignment"),
			"languages": request.form.get("languages")
		}
		character = generate_character(data)

	return render_template(
		"index.html",
		races=RACES,
		classes=CLASSES,
		subclasses=json.dumps(SUBCLASSES),
		backgrounds=BACKGROUNDS,
		alignments=ALIGNMENTS,
		character=character
	)

@app.route("/pdf", methods=["POST"])
def export_pdf():
	character = eval(request.form["character"])  # safe enough for local use

	template = "res/DnD_2024_Character-Sheet R2.pdf"
	reader = PdfReader(template)
	writer = PdfWriter()
	writer.append_pages_from_reader(reader)

	writer._root_object[NameObject("/AcroForm")] = reader.trailer["/Root"]["/AcroForm"]
	writer._root_object["/AcroForm"][NameObject("/NeedAppearances")] = BooleanObject(True)

	field_data = {
		"CharacterName_Field": character["Name"],
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

		"STR_Mod_Field": get_ability_modifier_str(character["Abilities"]["STR"]),
		"DEX_Mod_Field": get_ability_modifier_str(character["Abilities"]["DEX"]),
		"CON_Mod_Field": get_ability_modifier_str(character["Abilities"]["CON"]),
		"INT_Mod_Field": get_ability_modifier_str(character["Abilities"]["INT"]),
		"WIS_Mod_Field": get_ability_modifier_str(character["Abilities"]["WIS"]),
		"CHA_Mod_Field": get_ability_modifier_str(character["Abilities"]["CHA"]),

		"LVL_Field": str(character["Level"]),
		"ProficiencyBonus": "+"+str(get_proficiency_bonus(character["Level"])),

		"Traits_Field": str(character["Trait"]),
		#"Languages_Field": ", ".join(character["Languages"]),
		"Languages_Field": "Common",
	}

	for page in writer.pages:
		writer.update_page_form_field_values(page, field_data)

	tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
	with open(tmp.name, "wb") as f:
		writer.write(f)

	return send_file(tmp.name, as_attachment=True, download_name="character.pdf")

if __name__ == "__main__":
	app.run(host="0.0.0.0", port=5000)
