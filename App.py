# app.py
from flask import Flask, request, jsonify
import openai
import os
from werkzeug.utils import secure_filename
import pdfplumber  # pip install pdfplumber

# -------------------------------
# 1. CONFIGURATION
# -------------------------------
app = Flask(__name__)

# Folder where uploaded files will be temporarily saved
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {'pdf'}

# -------------------------------
# 2. OPENAI SETUP
# -------------------------------
openai.api_key = os.getenv("OPENAI_API_KEY")   # Set in environment
# openai.api_key = "sk-..."  # <-- OR hard-code (not for production)

# -------------------------------
# 3. SKILL MAP (Teacher → Job-Relevant Keywords)
# -------------------------------
SKILL_MAP = {
    "classroom management": [
        "behavior management", "positive reinforcement", "PBIS", "restorative practices",
        "differentiated discipline", "student engagement strategies"
    ],
    "curriculum design": [
        "lesson planning", "backward design", "standards alignment", "UDL", "scaffolding",
        "interdisciplinary units"
    ],
    "assessment": [
        "formative assessment", "summative assessment", "data-driven instruction",
        "rubric design", "progress monitoring", "IEP goals"
    ],
    "technology integration": [
        "Google Classroom", "SmartBoard", "EdTech", "blended learning", "LMS", "Kahoot",
        "Seesaw", "Flipgrid", "Nearpod"
    ],
    "differentiated instruction": [
        "tiered assignments", "learning styles", "multiple intelligences", "small group instruction",
        "flexible grouping", "accommodations"
    ],
    "parent communication": [
        "parent-teacher conferences", "newsletters", "Remind app", "ClassDojo", "email updates",
        "family engagement"
    ],
    "special education": [
        "IEP", "504 plans", "co-teaching", "inclusion", "behavior intervention plans",
        "accommodations vs modifications"
    ],
    "social-emotional learning": [
        "SEL", "growth mindset", "trauma-informed practices", "mindfulness", "character education"
    ]
}

# -------------------------------
# 4. HELPER FUNCTIONS
# -------------------------------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text.strip()

def expand_keywords(text, skill_map):
    expanded = text
    for generic, keywords in skill_map.items():
        if generic.lower() in text.lower():
            import random
            selected = random.sample(keywords, min(2, len(keywords)))
            for kw in selected:
                if kw not in expanded:
                    expanded += f" | {kw}"
    return expanded

def generate_tailored_resume(resume_text, job_description):
    prompt = f"""
You are an expert resume consultant for teachers.
Your task: Rewrite the teacher's resume to perfectly match the job description.

RULES:
1. Keep the teacher's name, contact info, and education unchanged.
2. Reorder and rephrase experience bullets to highlight skills from the job description.
3. Use strong action verbs and quantifiable achievements where possible.
4. Integrate relevant keywords naturally (from job description AND skill map).
5. Keep total length similar to original (don’t add fluff).
6. Output ONLY the final resume in clean, plain text.

RESUME:
{resume_text}

JOB DESCRIPTION:
{job_description}

TAILORED RESUME:
"""

    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a professional resume writer for educators."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.6,
        max_tokens=1500
    )
    return response.choices[0].message.content.strip()

# -------------------------------
# 5. ROUTES
# -------------------------------
@app.route('/')
def index():
    return '''
    <h2>TeacherPrep API</h2>
    <form method="post" action="/tailor" enctype="multipart/form-data">
        <p><input type="file" name="resume" accept=".pdf" required></p>
        <p><textarea name="job_description" placeholder="Paste job description here..." rows="10" cols="60" required></textarea></p>
        <p><button type="submit">Tailor My Resume</button></p>
    </form>
    '''

@app.route('/tailor', methods=['POST'])
def tailor_resume():
    if 'resume' not in request.files:
        return jsonify({"error": "No resume file uploaded"}), 400
    file = request.files['resume']
    job_desc = request.form.get('job_description', '').strip()

    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    if not job_desc:
        return jsonify({"error": "Job description is required"}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        resume_text = extract_text_from_pdf(filepath)
        if not resume_text.strip():
            os.remove(filepath)
            return jsonify({"error": "Could not extract text from PDF"}), 400

        resume_text = expand_keywords(resume_text, SKILL_MAP)

        try:
            tailored = generate_tailored_resume(resume_text, job_desc)
        except Exception as e:
            os.remove(filepath)
            return jsonify({"error": f"OpenAI error: {str(e)}"}), 500

        os.remove(filepath)

        return jsonify({
            "original_resume": resume_text[:1000] + "...",
            "tailored_resume": tailored
        })

    return jsonify({"error": "Invalid file type. Only PDF allowed."}), 400

# -------------------------------
# 6. RUN THE APP
# -------------------------------
if __name__ == '__main__':
    print("Starting TeacherPrep API...")
    print("Go to http://127.0.0.1:5000 in your browser")
    app.run(host='0.0.0.0', port=5000, debug=True)