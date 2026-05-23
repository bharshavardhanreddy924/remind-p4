try:
    from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
    from werkzeug.security import generate_password_hash, check_password_hash
    from werkzeug.utils import secure_filename
    from datetime import datetime, timedelta
    from bson.objectid import ObjectId
    import os
    import certifi
    from flask import g
    import uuid
    import json
    import glob
    import random
    from groq import Groq
    from dotenv import load_dotenv

except ImportError as e:
    print(f"Import error: {str(e)}")
    print("Please make sure all required packages are installed by running: pip install -r requirements.txt")
    exit(1)

# Load environment variables from .env file
load_dotenv()
print("Loading environment variables...")
print(f"GROQ_API_KEY loaded: {'Yes' if os.getenv('GROQ_API_KEY') else 'No'}")
print(f"MONGO_URI loaded: {'Yes' if os.getenv('MONGO_URI') else 'No'}")

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'memorycareappsecretkey')
app.permanent_session_lifetime = timedelta(days=7)

# Set secure headers for PWA
@app.after_request
def add_pwa_headers(response):
    # Add headers to help with PWA functionality
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'no-referrer-when-downgrade'
    response.headers['Permissions-Policy'] = 'geolocation=(), camera=()'
    
    # Disable browser caching so logged-out users can't click "back" into auth pages
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    return response

# Offline fallback page
@app.route('/offline')
def offline():
    return render_template('offline.html')

# MongoDB Configuration
from pymongo.mongo_client import MongoClient
# Use environment variable or fallback to hardcoded URI
uri = os.getenv('MONGO_URI', "mongodb+srv://bharshavardhanreddy924:516474Ta@data-dine.5oghq.mongodb.net/?retryWrites=true&w=majority&ssl=true")
print(f"Connecting to MongoDB...")

try:
    client = MongoClient(uri, tlsCAFile=certifi.where())
    # Send a ping to confirm a successful connection
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
    db = client['memorycare_db']
except Exception as e:
    print(f"MongoDB Connection Error: {e}")
    db = None  # Prevent application crashes

# File Upload Configuration
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads', 'uploaded')
OLD_IMAGES_FOLDER = os.path.join(BASE_DIR, 'static', 'images', 'slideshow')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OLD_IMAGES_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Database initialization
def init_db():
    # Create initial collections if they don't exist
    if db is not None:
        # Check if users collection has any documents
        if db.users.count_documents({}) == 0:
            print("Initializing database with default collections...")
            
            # Create initial admin user if no users exist
            db.users.insert_one({
                'name': 'Admin User',
                'email': 'admin@memorycare.com',
                'password': generate_password_hash('admin123'),
                'user_type': 'caretaker',
                'created_at': datetime.now(),
                'personal_info': 'Administrator account'
            })
            print("Created admin user")

# Initialize database
if db is not None:
    init_db()

# Helper functions
def check_db_connection():
    """Check if MongoDB connection is available and flash an error message if not"""
    if db is None:
        flash('Database connection error. Please try again later.', 'danger')
        return False
    return True

def get_user_data(user_id):
    if not check_db_connection() or db is None:
        return None
    return db.users.find_one({"_id": ObjectId(user_id)})

def get_caretaker_patients(caretaker_id):
    if not check_db_connection() or db is None:
        return []
    return list(db.users.find({"caretaker_id": ObjectId(caretaker_id)}))

def calculate_severity_score(mmse_score, observation_score, task_score):
    """Calculate severity score using weighted formula"""
    severity = (mmse_score * 0.60) + (observation_score * 0.25) + (task_score * 0.15)
    return round(severity, 2)

def classify_severity(score):
    """Classify severity level based on score"""
    if score >= 24:
        return {
            'level': 'Mild',
            'profile': 'Profile-A',
            'description': 'Mild cognitive impairment',
            'ui_mode': 'normal'
        }
    elif 18 <= score < 24:
        return {
            'level': 'Moderate',
            'profile': 'Profile-B',
            'description': 'Moderate cognitive impairment',
            'ui_mode': 'simplified'
        }
    else:
        return {
            'level': 'Severe',
            'profile': 'Profile-C',
            'description': 'Severe cognitive impairment',
            'ui_mode': 'assisted'
        }

def get_therapy_recommendations(severity_level):
    """Get therapy recommendations based on severity"""
    recommendations = {
        'Mild': [
            'Brain games and puzzles',
            'Memory recall exercises',
            'Attention and concentration tasks',
            'Reading and comprehension activities',
            'Social interaction activities'
        ],
        'Moderate': [
            'Guided memory exercises',
            'Daily routine reinforcement',
            'Simple problem-solving tasks',
            'Familiar object recognition',
            'Caregiver-assisted activities'
        ],
        'Severe': [
            'Audio-visual stimulation',
            'Sensory engagement activities',
            'Recognition exercises with familiar items',
            'Music therapy',
            'Caregiver-led interaction'
        ]
    }
    return recommendations.get(severity_level, [])

# Routes
@app.route('/splash')
def splash():
    """Serve the splash screen for PWA startup"""
    return render_template('splash.html')

@app.route('/')
def index():
    """Main entry point which can handle standalone parameter"""
    # Check if app is running in standalone mode
    standalone = request.args.get('standalone') == 'true'
    
    # Add standalone parameter to session if provided
    if standalone:
        session['standalone'] = True
    
    # Check if user is logged in, if so redirect to dashboard
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    # Otherwise show the login page
    return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Check if MongoDB connection is available
        if not check_db_connection() or db is None:
            return render_template('login.html')
            
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not email or not password:
            flash('Email and password are required', 'danger')
            return render_template('login.html')
        
        user = db.users.find_one({"email": email})
        
        if user:
            user_password = user.get('password')
            if user_password:
                try:
                    # Try to verify the password
                    if check_password_hash(user_password, password):
                        session.permanent = True
                        session['user_id'] = str(user['_id'])
                        session['user_type'] = user['user_type']
                        session['name'] = user['name']
                        
                        flash('Login successful!', 'success')
                        return redirect(url_for('dashboard'))
                    else:
                        flash('Invalid email or password', 'danger')
                except ValueError:
                    # If hash format is incompatible, rehash the password
                    # For now, just show error and suggest re-registration
                    flash('Password format incompatible. Please contact administrator or re-register.', 'danger')
            else:
                flash('Invalid email or password', 'danger')
        else:
            flash('Invalid email or password', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Check if MongoDB connection is available
        if not check_db_connection() or db is None:
            return render_template('register.html')
            
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        user_type = request.form.get('user_type')
        
        if not name or not email or not password or not user_type:
            flash('All fields are required', 'danger')
            return redirect(url_for('register'))
        
        # Check if email already exists
        if db.users.find_one({"email": email}):
            flash('Email already exists', 'danger')
            return redirect(url_for('register'))
        
        # Create new user
        new_user = {
            "name": name,
            "email": email,
            "password": generate_password_hash(password),
            "user_type": user_type,
            "created_at": datetime.now(),
            "personal_info": "I am a person who needs memory care assistance.",
            "cognitive_profile": None,
            "ui_mode": "normal"
        }
        
        # For patient-type users, allow caretaker assignment
        if user_type == "user" and request.form.get('caretaker_email') and db is not None:
            caretaker = db.users.find_one({"email": request.form.get('caretaker_email'), "user_type": "caretaker"})
            if caretaker:
                new_user["caretaker_id"] = caretaker['_id']
            else:
                flash('Caretaker email not found', 'warning')
        
        user_id = db.users.insert_one(new_user).inserted_id
        
        # Initialize collections for the user
        if db is not None:
            db.tasks.insert_one({
            "user_id": user_id,
            "tasks": [
                {"text": "Take morning medication", "completed": False},
                {"text": "Do 15 minutes of memory exercises", "completed": False},
                {"text": "Walk for 30 minutes", "completed": False},
                {"text": "Call family member", "completed": False},
                {"text": "Read for 20 minutes", "completed": False}
            ]
            })
            
            db.medications.insert_one({
                "user_id": user_id,
                "medications": []
            })
            
            db.notes.insert_one({
                "user_id": user_id,
                "content": "",
                "updated_at": datetime.now()
            })
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Check MongoDB connection
    if not check_db_connection():
        return redirect(url_for('logout'))
    
    user_id = session['user_id']
    user_type = session['user_type']
    
    if user_type == 'caretaker':
        patients = get_caretaker_patients(ObjectId(user_id))
        return render_template('dashboard.html', patients=patients)
    else:
        user = get_user_data(ObjectId(user_id))
        if user is None:
            flash('User data not found. Please try logging in again.', 'danger')
            return redirect(url_for('logout'))
        
        # Get user's task data
        task_data = db.tasks.find_one({"user_id": ObjectId(user_id)}) if db is not None else None
        if not task_data:
            task_data = {"tasks": []}
        
        # Get medication data
        med_data = db.medications.find_one({"user_id": ObjectId(user_id)}) if db is not None else None
        if not med_data:
            med_data = {"medications": []}
        
        # Current date info
        today = datetime.now()
        formatted_date = today.strftime("%A, %B %d, %Y")
        
        return render_template('dashboard.html', 
                               user=user, 
                               tasks=task_data['tasks'], 
                               medications=med_data['medications'],
                               date=formatted_date)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

@app.route('/tasks', methods=['GET', 'POST'])
def tasks():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if not check_db_connection() or db is None:
        flash('Database connection error', 'danger')
        return redirect(url_for('dashboard'))
    
    user_id = ObjectId(session['user_id'])
    
    if request.method == 'POST':
        if request.form.get('action') == 'add':
            task_text = request.form.get('task_text')
            
            db.tasks.update_one(
                {"user_id": user_id},
                {"$push": {"tasks": {"text": task_text, "completed": False}}}
            )
            flash('Task added successfully', 'success')
        
        elif request.form.get('action') == 'update':
            task_index_str = request.form.get('task_index')
            if not task_index_str:
                flash('Invalid task index', 'danger')
                return redirect(url_for('tasks'))
            task_index = int(task_index_str)
            task_status = 'completed' in request.form
            
            # Get existing tasks
            task_data = db.tasks.find_one({"user_id": user_id})
            tasks = task_data.get('tasks', []) if task_data else []
            
            # Update specific task status
            if 0 <= task_index < len(tasks):
                tasks[task_index]['completed'] = task_status
                
                # Update in database
                db.tasks.update_one(
                    {"user_id": user_id},
                    {"$set": {"tasks": tasks}}
                )
                flash('Task updated', 'success')
        
        elif request.form.get('action') == 'delete':
            task_index_str = request.form.get('task_index')
            if not task_index_str:
                flash('Invalid task index', 'danger')
                return redirect(url_for('tasks'))
            task_index = int(task_index_str)
            
            # Get existing tasks
            task_data = db.tasks.find_one({"user_id": user_id})
            tasks = task_data.get('tasks', []) if task_data else []
            
            # Remove specific task
            if 0 <= task_index < len(tasks):
                tasks.pop(task_index)
                
                # Update in database
                db.tasks.update_one(
                    {"user_id": user_id},
                    {"$set": {"tasks": tasks}}
                )
                flash('Task deleted', 'success')
    
    # Get updated task list
    task_data = db.tasks.find_one({"user_id": user_id})
    tasks = task_data.get('tasks', []) if task_data else []
    
    return render_template('tasks.html', tasks=tasks)

@app.route('/medications', methods=['GET', 'POST'])
def medications():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if not check_db_connection() or db is None:
        flash('Database connection error', 'danger')
        return redirect(url_for('dashboard'))
    
    user_id = ObjectId(session['user_id'])
    
    if request.method == 'POST':
        if request.form.get('action') == 'add':
            med_name = request.form.get('med_name')
            med_time = request.form.get('med_time')
            
            if med_name and med_time:
                # Validate time format
                try:
                    # Try to parse the time to validate format
                    time_obj = datetime.strptime(med_time, '%I:%M %p')
                    
                    new_med = {
                        "id": str(datetime.now().timestamp()),
                        "name": med_name,
                        "time": med_time,
                    }
                    
                    db.medications.update_one(
                        {"user_id": user_id},
                        {"$push": {"medications": new_med}},
                        upsert=True
                    )
                    
                    flash('Medication added successfully', 'success')
                except ValueError:
                    flash('Invalid time format. Please use HH:MM AM/PM', 'danger')
        
        elif request.form.get('action') == 'delete':
            med_id = request.form.get('med_id')
            
            db.medications.update_one(
                {"user_id": user_id},
                {"$pull": {"medications": {"id": med_id}}}
            )
            
            flash('Medication deleted', 'success')
    
    # Get updated medication list
    med_data = db.medications.find_one({"user_id": user_id})
    if not med_data:
        medications = []
    else:
        medications = med_data.get('medications', [])
        
        # Sort medications by time
        def time_key(med):
            try:
                return datetime.strptime(med['time'], '%I:%M %p').time()
            except:
                return datetime.min.time()
                
        medications = sorted(medications, key=time_key)
    
    return render_template('medications.html', medications=medications)

@app.route('/ai_assistant')
def ai_assistant():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = ObjectId(session['user_id'])
    user = get_user_data(user_id)
    
    return render_template('ai_assistant.html', user=user)

@app.route('/ai_response', methods=['POST'])
def ai_response():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    
    if not check_db_connection() or db is None:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    
    user_id = ObjectId(session['user_id'])
    user = get_user_data(user_id)
    
    data = request.json
    user_message = data.get('prompt', '').strip()
    conversation_history = data.get('conversation_history', [])
    
    if not user_message:
        return jsonify({'success': False, 'message': 'Empty message'}), 400
    
    # Store user message in conversation history
    conversation_entry = {
        'user_id': user_id,
        'timestamp': datetime.now(),
        'user_message': user_message,
        'context_type': 'conversation'
    }
    # Auto-store statements about self silently (LLM will acknowledge naturally)
    auto_store_patterns = ['my name is', 'i am', 'i live in', 'my age is', 'i like', 'my hobby is', 'my favorite', 'remember that', 'note that']
    should_auto_store = any(pattern in user_message.lower() for pattern in auto_store_patterns)
    
    if should_auto_store:
        # Silently store the information - LLM will acknowledge it naturally
        db.user_context.insert_one({
            'user_id': user_id,
            'timestamp': datetime.now(),
            'information': user_message,
            'category': 'user_provided',
            'extracted': True
        })
    
    # Always retrieve comprehensive user data from all collections
    context_info = []
    
    # 1. Basic user profile
    if user:
        context_info.append(f"Name: {user.get('name', 'Unknown')}")
        context_info.append(f"Email: {user.get('email', 'Not set')}")
        if user.get('age'):
            context_info.append(f"Age: {user.get('age')}")
        if user.get('personal_info'):
            context_info.append(f"Personal Info: {user.get('personal_info')}")
    
    # 2. User context (stored information)
    user_contexts = list(db.user_context.find(
        {"user_id": user_id}
    ).sort("timestamp", -1).limit(15))
    
    if user_contexts:
        context_info.append("\nStored Information:")
        for ctx in user_contexts:
            context_info.append(f"- {ctx.get('information', '')}")
    
    # 3. MMSE Assessment data
        latest_mmse = db.mmse_results.find_one(
            {"user_id": user_id},
            sort=[("timestamp", -1)]
        )
        if latest_mmse:
            context_info.append(f"\nCognitive Assessment:")
            context_info.append(f"- MMSE Score: {latest_mmse.get('total_score', 'N/A')}/30")
            context_info.append(f"- Assessment Date: {latest_mmse.get('timestamp', 'Unknown')}")
        
        # 4. Severity assessment
        latest_severity = db.severity_assessments.find_one(
            {"user_id": user_id},
            sort=[("timestamp", -1)]
        )
        if latest_severity:
            context_info.append(f"- Severity Level: {latest_severity.get('severity_level', 'Unknown')}")
            context_info.append(f"- Cognitive Profile: {latest_severity.get('ui_profile', 'Unknown')}")
        
        # 5. Tasks
        task_data = db.tasks.find_one({"user_id": user_id})
        if task_data and task_data.get('tasks'):
            tasks = task_data.get('tasks', [])
            pending_tasks = [t for t in tasks if not t.get('completed', False)]
            if pending_tasks:
                context_info.append(f"\nPending Tasks: {len(pending_tasks)}")
                for task in pending_tasks[:3]:  # Show first 3
                    context_info.append(f"- {task.get('text', 'Unknown task')}")
        
        # 6. Medications
        med_data = db.medications.find_one({"user_id": user_id})
        if med_data and med_data.get('medications'):
            meds = med_data.get('medications', [])
            if meds:
                context_info.append(f"\nMedications: {len(meds)}")
                for med in meds[:3]:  # Show first 3
                    context_info.append(f"- {med.get('name', 'Unknown')} at {med.get('time', 'Unknown time')}")
        
        # 7. Notes
        notes_data = db.notes.find_one({"user_id": user_id})
        if notes_data and notes_data.get('content'):
            notes_preview = notes_data.get('content', '')[:200]
            context_info.append(f"\nNotes: {notes_preview}...")
        
        # 8. Recent conversations
        recent_convos = list(db.ai_conversations.find(
            {"user_id": user_id}
        ).sort("timestamp", -1).limit(5))
        
        if recent_convos:
            context_info.append("\nRecent Conversations:")
            for convo in recent_convos:
                if convo.get('user_message'):
                    context_info.append(f"User: {convo.get('user_message')}")
                if convo.get('ai_response'):
                    context_info.append(f"AI: {convo.get('ai_response')}")
        
    context_string = "\n".join(context_info)
    
    # ALWAYS use Groq LLM for intelligent, natural responses with conversation history
    response_text = generate_contextual_response(user_message, context_string, user, conversation_history, is_storing=should_auto_store)
    
    # Extract and store important information from the conversation
    extract_and_store_important_info(user_id, user_message, response_text)
    
    # Store AI response
    conversation_entry['ai_response'] = response_text
    db.ai_conversations.insert_one(conversation_entry)
    
    return jsonify({'success': True, 'response': response_text})

def extract_and_store_important_info(user_id, user_message, ai_response):
    """Extract important information from conversation and store in user notes"""
    try:
        groq_api_key = os.getenv('GROQ_API_KEY')
        if not groq_api_key:
            return
        
        client = Groq(api_key=groq_api_key)
        
        # Ask LLM to extract important information
        extraction_prompt = f"""Analyze this conversation and extract ONLY important personal information that should be remembered long-term.

User said: "{user_message}"
AI responded: "{ai_response}"

Extract information like:
- Personal details (name, age, location, family)
- Preferences (likes, dislikes, hobbies)
- Important facts (medical info, routines, memories)
- Relationships (family members, friends)

Return ONLY the extracted facts in a simple bullet list format. If there's nothing important to extract, return "NONE".

Examples:
- "User's name is John"
- "User is 65 years old"
- "User lives in California"
- "User likes gardening"
- "User's daughter is named Sarah"

Extract now:"""

        extraction = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are an information extraction assistant. Extract only factual, important information."},
                {"role": "user", "content": extraction_prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.3,
            max_tokens=150
        )
        
        extracted_info = extraction.choices[0].message.content.strip()
        
        # Only store if there's actual information
        if extracted_info and extracted_info != "NONE" and len(extracted_info) > 5:
            # Get or create user notes document
            notes_doc = db.notes.find_one({"user_id": user_id})
            
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
            new_entry = f"\n\n[Auto-extracted {current_time}]\n{extracted_info}"
            
            if notes_doc:
                # Append to existing notes
                current_content = notes_doc.get('content', '')
                updated_content = current_content + new_entry
                
                db.notes.update_one(
                    {"user_id": user_id},
                    {"$set": {
                        "content": updated_content,
                        "updated_at": datetime.now()
                    }}
                )
            else:
                # Create new notes document
                db.notes.insert_one({
                    "user_id": user_id,
                    "content": f"# Important Information{new_entry}",
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                })
            
            print(f"Extracted and stored: {extracted_info[:50]}...")
    
    except Exception as e:
        print(f"Error extracting information: {e}")
        # Don't fail the main conversation if extraction fails

def generate_contextual_response(user_message, context, user, conversation_history=None, is_storing=False):
    """Generate a contextual response using Groq LLM with stored context and conversation history"""
    try:
        # Initialize Groq client
        groq_api_key = os.getenv('GROQ_API_KEY')
        if not groq_api_key:
            print("GROQ_API_KEY not found - falling back to basic responses")
            return generate_fallback_response(user_message, context, user)
        
        print(f"Using Groq API with key: {groq_api_key[:20]}...")
        client = Groq(api_key=groq_api_key)
        
        # Build system prompt with user context
        system_prompt = f"""You are a compassionate AI memory assistant for a dementia care application.

CRITICAL INSTRUCTIONS:
- ALWAYS check conversation history FIRST for recent information
- Use the profile data below for stored long-term information
- Keep responses SHORT and DIRECT (1-2 sentences maximum)
- Be warm but concise
- Don't over-explain or ramble
- Answer the question directly without extra suggestions

USER'S COMPLETE PROFILE:
{context if context else 'No information available yet'}

RESPONSE STYLE:
- Direct answers only
- No unnecessary questions back to user
- No suggestions unless asked
- Simple, clear language
- Warm but brief

Examples:
- "What color cat did I see?" → "You saw a white cat."
- "How old am I?" → "You're 21 years old."
- "Where do I live?" → "You live in Kengeri."
- "I saw a white cat" → "That's lovely! I've saved that for you."

REMEMBER: Be helpful, not chatty. Answer directly and move on.
"""

        # Build messages array with conversation history
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history if available (last 8 messages for context)
        if conversation_history and len(conversation_history) > 0:
            # Take last 8 messages to maintain context without overwhelming the model
            recent_history = conversation_history[-8:] if len(conversation_history) > 8 else conversation_history
            for msg in recent_history:
                messages.append({
                    "role": msg.get('role', 'user'),
                    "content": msg.get('content', '')
                })
        else:
            # If no history, just add current message
            messages.append({"role": "user", "content": user_message})
        
        # Call Groq API
        chat_completion = client.chat.completions.create(
            messages=messages,
            model="llama-3.3-70b-versatile",  # Updated to supported model (Dec 2024)
            temperature=0.7,
            max_tokens=250,
            top_p=0.9
        )
        
        response = chat_completion.choices[0].message.content
        print(f"Groq response generated successfully")
        return response.strip()
        
    except Exception as e:
        print(f"Groq API Error: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        # Fallback to basic responses
        return generate_fallback_response(user_message, context, user)

def generate_fallback_response(user_message, context, user):
    """Fallback response generator when Groq API is unavailable"""
    message_lower = user_message.lower()
    
    # Name queries
    if 'name' in message_lower and ('my' in message_lower or 'what' in message_lower):
        return f"Your name is {user.get('name', 'not set in your profile')}."
    
    # Age queries
    if 'age' in message_lower or 'old' in message_lower:
        return "I don't have your age information stored yet. You can tell me by saying 'My age is [number]'."
    
    # Location queries
    if 'live' in message_lower or 'address' in message_lower or 'where' in message_lower:
        return "I don't have your address stored yet. You can tell me by saying 'I live in [location]'."
    
    # Personal info queries
    if 'about' in message_lower and ('me' in message_lower or 'myself' in message_lower):
        personal_info = user.get('personal_info', 'No personal information available yet.')
        return f"Here's what I know about you: {personal_info}"
    
    # Hobby queries
    if 'hobby' in message_lower or 'hobbies' in message_lower or 'like to do' in message_lower:
        return "I don't have information about your hobbies yet. You can tell me by saying 'My hobbies are [hobbies]' or 'I like to [activity]'."
    
    # Family queries
    if 'family' in message_lower:
        return "I don't have information about your family yet. You can tell me about them by saying 'My family includes [family members]'."
    
    # Medication queries
    if 'medication' in message_lower or 'medicine' in message_lower:
        return "You can check your medications in the Medications section of the app. Would you like me to help you with anything else?"
    
    # Task queries
    if 'task' in message_lower or 'todo' in message_lower:
        return "You can view and manage your tasks in the Tasks section. Is there anything specific you'd like to know?"
    
    # General greeting
    if any(word in message_lower for word in ['hello', 'hi', 'hey', 'good morning', 'good afternoon']):
        return f"Hello {user.get('name', 'there')}! How can I assist you today?"
    
    # Thank you
    if 'thank' in message_lower:
        return "You're welcome! I'm here to help whenever you need me."
    
    # Help request
    if 'help' in message_lower:
        return "I can help you remember personal information, answer questions about yourself, and store new information you tell me. Just ask me anything or tell me something you'd like me to remember!"
    
    # Default response with context
    if context:
        return f"Based on what I know: {context[:200]}... Is there something specific you'd like to know?"
    else:
        return "I'm here to help! You can ask me questions about yourself, or tell me things you'd like me to remember. For example, try saying 'My name is...' or 'I like to...'"

@app.route('/memory_training')
def memory_training():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = ObjectId(session['user_id'])
    user = get_user_data(user_id)
    
    return render_template('memory_training.html', user=user)

@app.route('/process_voice_navigation', methods=['POST'])
def process_voice_navigation():
    """Process voice navigation commands using Groq LLM"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    
    if not check_db_connection() or db is None:
        return jsonify({'success': False, 'message': 'Database error'}), 500
    
    user_id = ObjectId(session['user_id'])
    user = get_user_data(user_id)
    
    data = request.json
    command = data.get('command', '').strip().lower()
    
    if not command:
        return jsonify({'success': False, 'message': 'No command provided'}), 400
    
    try:
        # Use Groq LLM to intelligently parse the command
        groq_api_key = os.getenv('GROQ_API_KEY')
        if groq_api_key:
            client = Groq(api_key=groq_api_key)
            
            system_prompt = """You are a voice navigation assistant for a dementia care application. 
Your job is to understand user voice commands and map them to the correct navigation action.

Available pages and their routes:
- Dashboard/Home: /dashboard
- Tasks: /tasks
- Medications/Medicine: /medications
- Photos/Memories/Slideshow: /photo_slideshow
- MMSE Test/Assessment/Cognitive Test: /mmse_assessment
- Progress/Analytics/Dashboard: /progress_dashboard
- Memory Training/Games: /memory_training
- AI Assistant/Chatbot: /ai_assistant
- Notes: /notes

User intent examples:
- "take me to tasks" → /tasks
- "show my medications" → /medications
- "I want to see photos" → /photo_slideshow
- "take the MMSE test" → /mmse_assessment
- "show my progress" → /progress_dashboard
- "go home" → /dashboard
- "open memory games" → /memory_training
- "talk to assistant" → /ai_assistant

Respond ONLY with a JSON object in this exact format:
{"route": "/route_name", "message": "Navigating to [page name]"}

If you cannot understand the command, respond with:
{"route": null, "message": "I didn't understand that. Try saying 'take me to tasks' or 'show my photos'"}
"""
            
            chat_completion = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"User said: {command}"}
                ],
                model="llama-3.1-70b-versatile",
                temperature=0.3,
                max_tokens=100
            )
            
            response_text = chat_completion.choices[0].message.content.strip()
            
            # Parse JSON response
            import json
            try:
                result = json.loads(response_text)
                route = result.get('route')
                message = result.get('message', 'Navigating...')
                
                if route:
                    return jsonify({
                        'success': True,
                        'url': route,
                        'message': message
                    })
                else:
                    return jsonify({
                        'success': False,
                        'message': message
                    })
            except json.JSONDecodeError:
                # Fallback if LLM doesn't return valid JSON
                return process_voice_navigation_fallback(command)
        else:
            # No Groq API key, use fallback
            return process_voice_navigation_fallback(command)
            
    except Exception as e:
        print(f"Voice navigation error: {e}")
        return process_voice_navigation_fallback(command)

def process_voice_navigation_fallback(command):
    """Fallback navigation processing without LLM"""
    command = command.lower()
    
    # Navigation mapping
    navigation_map = {
        'dashboard': ('/dashboard', 'Going to dashboard'),
        'home': ('/dashboard', 'Going home'),
        'task': ('/tasks', 'Opening your tasks'),
        'medication': ('/medications', 'Showing your medications'),
        'medicine': ('/medications', 'Showing your medications'),
        'photo': ('/photo_slideshow', 'Opening photo memories'),
        'picture': ('/photo_slideshow', 'Opening photo memories'),
        'memory': ('/photo_slideshow', 'Opening photo memories'),
        'slideshow': ('/photo_slideshow', 'Starting slideshow'),
        'mmse': ('/mmse_assessment', 'Opening MMSE assessment'),
        'test': ('/mmse_assessment', 'Opening cognitive test'),
        'assessment': ('/mmse_assessment', 'Opening assessment'),
        'progress': ('/progress_dashboard', 'Showing your progress'),
        'analytics': ('/progress_dashboard', 'Opening analytics'),
        'training': ('/memory_training', 'Opening memory training'),
        'game': ('/memory_training', 'Opening memory games'),
        'assistant': ('/ai_assistant', 'Opening AI assistant'),
        'chatbot': ('/ai_assistant', 'Opening chatbot'),
        'chat': ('/ai_assistant', 'Opening chat'),
        'note': ('/notes', 'Opening your notes'),
    }
    
    # Find matching route
    for keyword, (route, message) in navigation_map.items():
        if keyword in command:
            return jsonify({
                'success': True,
                'url': route,
                'message': message
            })
    
    # No match found
    return jsonify({
        'success': False,
        'message': 'I didn\'t understand that. Try saying "take me to tasks" or "show my photos"'
    })

    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    return render_template('memory_training.html')

@app.route('/notes', methods=['GET', 'POST'])
def notes():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if not check_db_connection() or db is None:
        flash('Database connection error', 'danger')
        return redirect(url_for('dashboard'))
    
    user_id = ObjectId(session['user_id'])
    
    if request.method == 'POST':
        content = request.form.get('content')
        
        db.notes.update_one(
            {"user_id": user_id},
            {"$set": {"content": content, "updated_at": datetime.now()}},
            upsert=True
        )
        
        flash('Notes saved successfully', 'success')
    
    # Get user's notes
    notes_data = db.notes.find_one({"user_id": user_id})
    if not notes_data:
        content = ""
    else:
        content = notes_data.get('content', "")
    
    return render_template('notes.html', content=content)

# ==================== PHOTO SLIDESHOW ROUTES ====================

def get_old_images():
    """Get list of old images for slideshow"""
    image_files = []
    for ext in ['jpg', 'jpeg', 'png', 'gif']:
        image_files.extend(glob.glob(os.path.join(OLD_IMAGES_FOLDER, f"*.{ext}")))
    
    # Return relative paths for Flask static files
    return [os.path.relpath(f, 'remindp2/static').replace('\\', '/') for f in image_files]

def get_memory_prompts(count=3):
    """Generate random memory prompts"""
    prompts = [
        "What was your favorite childhood memory?",
        "Tell me about your first job or career.",
        "What was your wedding day like?",
        "Describe your childhood home.",
        "What games did you play as a child?",
        "Tell me about your school days.",
        "What was your favorite holiday tradition?",
        "Describe a memorable family gathering.",
        "What was your favorite song or music?",
        "Tell me about a special friend from your past.",
        "What was your favorite food growing up?",
        "Describe a memorable vacation or trip.",
        "What hobbies did you enjoy?",
        "Tell me about your parents or grandparents.",
        "What was fashion like when you were young?"
    ]
    return random.sample(prompts, min(count, len(prompts)))

@app.route('/photo_slideshow')
def photo_slideshow():
    """Main page for photo slideshow / reminiscence therapy"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Get old images for the slideshow
    old_images = get_old_images()
    
    # Generate memory prompts
    memory_prompts = get_memory_prompts(3)
    
    # Get user info
    user_id = ObjectId(session['user_id'])
    user = get_user_data(user_id)
    
    # Get memory entries from database
    memory_entries = list(db.memory_entries.find({"user_id": user_id}).sort("date", -1))
    
    return render_template('photo_slideshow.html',
                           old_images=old_images,
                           memory_prompts=memory_prompts,
                           memory_entries=memory_entries,
                           user=user)

@app.route('/upload_memory', methods=['POST'])
def upload_memory():
    """Upload a memory (photo) for reminiscence therapy"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = ObjectId(session['user_id'])
    
    if 'photo' not in request.files:
        flash("No file part", "danger")
        return redirect(url_for('photo_slideshow'))
    
    file = request.files['photo']
    year = request.form.get('year', '')
    description = request.form.get('description', '')
    
    if file.filename == '':
        flash("No selected file", "danger")
        return redirect(url_for('photo_slideshow'))
    
    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(file.filename)
            # Add year to filename if provided
            if year:
                base, ext = os.path.splitext(filename)
                filename = f"{base}_{year}{ext}"
            
            file_path = os.path.join(OLD_IMAGES_FOLDER, filename)
            file.save(file_path)
            
            # Save metadata to database
            db.memory_entries.insert_one({
                "user_id": user_id,
                "filename": filename,
                "path": os.path.relpath(file_path, 'remindp2/static').replace('\\', '/'),
                "year": year,
                "description": description,
                "date": datetime.now()
            })
            
            flash("Memory uploaded successfully!", "success")
        except Exception as e:
            flash(f"Error uploading memory: {str(e)}", "danger")
    else:
        flash("File type not allowed. Please upload a jpg, jpeg, png, or gif file.", "danger")
    
    return redirect(url_for('photo_slideshow'))

@app.route('/add_memory_entry', methods=['POST'])
def add_memory_entry():
    """Add a text memory entry without a photo"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = ObjectId(session['user_id'])
    title = request.form.get('title', '')
    year = request.form.get('year', '')
    content = request.form.get('content', '')
    
    if not title or not content:
        flash("Title and content are required", "danger")
        return redirect(url_for('photo_slideshow'))
    
    try:
        db.memory_entries.insert_one({
            "user_id": user_id,
            "title": title,
            "year": year,
            "content": content,
            "date": datetime.now()
        })
        flash("Memory entry added successfully!", "success")
    except Exception as e:
        flash(f"Error adding memory entry: {str(e)}", "danger")
    
    return redirect(url_for('photo_slideshow'))

# ==================== MMSE ASSESSMENT ROUTES ====================

@app.route('/mmse_assessment')
def mmse_assessment():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    return render_template('mmse_assessment.html')

@app.route('/mmse_onboarding', methods=['GET', 'POST'])
def mmse_onboarding():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        if not check_db_connection() or db is None:
            flash('Database connection error', 'danger')
            return redirect(url_for('dashboard'))
        
        user_id = ObjectId(session['user_id'])
        
        onboarding_data = {
            'user_id': user_id,
            'full_name': request.form.get('full_name'),
            'age': int(request.form.get('age', 0)),
            'gender': request.form.get('gender'),
            'education_level': request.form.get('education_level'),
            'preferred_language': request.form.get('preferred_language'),
            'caregiver_available': request.form.get('caregiver_available') == 'yes',
            'medical_notes': request.form.get('medical_notes', ''),
            'created_at': datetime.now()
        }
        
        db.mmse_onboarding.update_one(
            {"user_id": user_id},
            {"$set": onboarding_data},
            upsert=True
        )
        
        flash('Onboarding completed successfully!', 'success')
        return redirect(url_for('mmse_test'))
    
    return render_template('mmse_onboarding.html')

@app.route('/mmse_test', methods=['GET', 'POST'])
def mmse_test():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        if not check_db_connection() or db is None:
            return jsonify({'success': False, 'message': 'Database error'}), 500
        
        user_id = ObjectId(session['user_id'])
        
        # Calculate MMSE score
        mmse_data = request.json
        
        # Orientation to Time (5 marks)
        time_score = sum([
            1 if mmse_data.get('date_correct') else 0,
            1 if mmse_data.get('month_correct') else 0,
            1 if mmse_data.get('year_correct') else 0,
            1 if mmse_data.get('day_correct') else 0,
            1 if mmse_data.get('season_correct') else 0
        ])
        
        # Orientation to Place (5 marks)
        place_score = sum([
            1 if mmse_data.get('country_correct') else 0,
            1 if mmse_data.get('state_correct') else 0,
            1 if mmse_data.get('building_correct') else 0,
            1 if mmse_data.get('floor_correct') else 0,
            1 if mmse_data.get('area_correct') else 0
        ])
        
        # Registration (3 marks)
        registration_score = mmse_data.get('registration_score', 0)
        
        # Attention & Calculation (5 marks)
        attention_score = mmse_data.get('attention_score', 0)
        
        # Recall (3 marks)
        recall_score = mmse_data.get('recall_score', 0)
        
        # Language (8 marks)
        language_score = mmse_data.get('language_score', 0)
        
        # Visual Construction (1 mark)
        visual_score = 1 if mmse_data.get('visual_correct') else 0
        
        total_mmse_score = time_score + place_score + registration_score + attention_score + recall_score + language_score + visual_score
        
        # Store MMSE results
        mmse_result = {
            'user_id': user_id,
            'test_date': datetime.now(),
            'time_score': time_score,
            'place_score': place_score,
            'registration_score': registration_score,
            'attention_score': attention_score,
            'recall_score': recall_score,
            'language_score': language_score,
            'visual_score': visual_score,
            'total_score': total_mmse_score,
            'responses': mmse_data
        }
        
        db.mmse_results.insert_one(mmse_result)
        
        return jsonify({
            'success': True,
            'total_score': total_mmse_score,
            'redirect': url_for('caregiver_observation')
        })
    
    return render_template('mmse_test.html')

@app.route('/caregiver_observation', methods=['GET', 'POST'])
def caregiver_observation():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        if not check_db_connection() or db is None:
            return jsonify({'success': False, 'message': 'Database error'}), 500
        
        user_id = ObjectId(session['user_id'])
        
        # Calculate observation score (normalize to 30)
        observations = request.json
        
        total_raw = sum([
            int(observations.get('forgetfulness', 0)),
            int(observations.get('mood_instability', 0)),
            int(observations.get('wandering', 0)),
            int(observations.get('recognition_difficulty', 0)),
            int(observations.get('task_dependency', 0)),
            int(observations.get('communication_difficulty', 0))
        ])
        
        # Normalize to 30 (6 questions * 5 points = 30 max)
        observation_score = total_raw
        
        # Store observation results
        observation_result = {
            'user_id': user_id,
            'observation_date': datetime.now(),
            'forgetfulness': int(observations.get('forgetfulness', 0)),
            'mood_instability': int(observations.get('mood_instability', 0)),
            'wandering': int(observations.get('wandering', 0)),
            'recognition_difficulty': int(observations.get('recognition_difficulty', 0)),
            'task_dependency': int(observations.get('task_dependency', 0)),
            'communication_difficulty': int(observations.get('communication_difficulty', 0)),
            'total_score': observation_score
        }
        
        db.caregiver_observations.insert_one(observation_result)
        
        return jsonify({
            'success': True,
            'observation_score': observation_score,
            'redirect': url_for('cognitive_tasks')
        })
    
    return render_template('caregiver_observation.html')

@app.route('/cognitive_tasks', methods=['GET', 'POST'])
def cognitive_tasks():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        if not check_db_connection() or db is None:
            return jsonify({'success': False, 'message': 'Database error'}), 500
        
        user_id = ObjectId(session['user_id'])
        
        # Calculate task performance score (normalize to 30)
        task_data = request.json
        
        accuracy = float(task_data.get('accuracy', 0))
        time_score = float(task_data.get('time_score', 0))
        completion_rate = float(task_data.get('completion_rate', 0))
        
        # Weighted task score (normalize to 30)
        task_score = (accuracy * 0.5 + time_score * 0.3 + completion_rate * 0.2) * 30
        
        # Store task results
        task_result = {
            'user_id': user_id,
            'task_date': datetime.now(),
            'accuracy': accuracy,
            'time_score': time_score,
            'completion_rate': completion_rate,
            'total_score': round(task_score, 2),
            'task_details': task_data
        }
        
        db.cognitive_task_results.insert_one(task_result)
        
        return jsonify({
            'success': True,
            'task_score': round(task_score, 2),
            'redirect': url_for('severity_assessment')
        })
    
    return render_template('cognitive_tasks.html')

@app.route('/severity_assessment')
def severity_assessment():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if not check_db_connection() or db is None:
        flash('Database connection error', 'danger')
        return redirect(url_for('dashboard'))
    
    user_id = ObjectId(session['user_id'])
    
    # Get latest scores
    mmse_result = db.mmse_results.find_one({"user_id": user_id}, sort=[("test_date", -1)])
    observation_result = db.caregiver_observations.find_one({"user_id": user_id}, sort=[("observation_date", -1)])
    task_result = db.cognitive_task_results.find_one({"user_id": user_id}, sort=[("task_date", -1)])
    
    if not mmse_result or not observation_result or not task_result:
        flash('Please complete all assessments first', 'warning')
        return redirect(url_for('mmse_onboarding'))
    
    mmse_score = mmse_result['total_score']
    observation_score = observation_result['total_score']
    task_score = task_result['total_score']
    
    # Calculate severity
    severity_score = calculate_severity_score(mmse_score, observation_score, task_score)
    classification = classify_severity(severity_score)
    recommendations = get_therapy_recommendations(classification['level'])
    
    # Store severity assessment
    severity_data = {
        'user_id': user_id,
        'assessment_date': datetime.now(),
        'mmse_score': mmse_score,
        'observation_score': observation_score,
        'task_score': task_score,
        'final_score': severity_score,
        'severity_level': classification['level'],
        'ui_profile': classification['profile'],
        'ui_mode': classification['ui_mode']
    }
    
    db.severity_assessments.insert_one(severity_data)
    
    # Update user profile
    db.users.update_one(
        {"_id": user_id},
        {"$set": {
            "cognitive_profile": classification['profile'],
            "ui_mode": classification['ui_mode'],
            "severity_level": classification['level']
        }}
    )
    
    return render_template('severity_assessment.html',
                          mmse_score=mmse_score,
                          observation_score=observation_score,
                          task_score=task_score,
                          severity_score=severity_score,
                          classification=classification,
                          recommendations=recommendations)

@app.route('/progress_dashboard')
def progress_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if not check_db_connection() or db is None:
        flash('Database connection error', 'danger')
        return redirect(url_for('dashboard'))
    
    user_id = ObjectId(session['user_id'])
    
    # Get all historical assessments
    severity_history = list(db.severity_assessments.find(
        {"user_id": user_id}
    ).sort("assessment_date", 1))
    
    mmse_history = list(db.mmse_results.find(
        {"user_id": user_id}
    ).sort("test_date", 1))
    
    # Calculate improvement
    improvement_data = None
    if len(severity_history) >= 2:
        latest = severity_history[-1]
        previous = severity_history[-2]
        
        score_change = latest['severity_score'] - previous['severity_score']
        improvement_percent = (score_change / previous['severity_score']) * 100 if previous['severity_score'] > 0 else 0
        
        improvement_data = {
            'score_change': round(score_change, 2),
            'improvement_percent': round(improvement_percent, 2),
            'trend': 'improving' if score_change > 0 else 'declining' if score_change < 0 else 'stable'
        }
    
    return render_template('progress_dashboard.html',
                          severity_history=severity_history,
                          mmse_history=mmse_history,
                          improvement_data=improvement_data)

# ==================== CARETAKER PATIENT MANAGEMENT ====================

@app.route('/manage_patient/<patient_id>')
def manage_patient(patient_id):
    if 'user_id' not in session or session.get('user_type') != 'caretaker':
        return redirect(url_for('login'))
    
    if not check_db_connection() or db is None:
        flash('Database connection error', 'danger')
        return redirect(url_for('dashboard'))
    
    try:
        patient_id_obj = ObjectId(patient_id)
        patient = get_user_data(patient_id_obj)
        
        if not patient:
            flash('Patient not found', 'danger')
            return redirect(url_for('dashboard'))
        
        # Get patient's task data
        task_data = db.tasks.find_one({"user_id": patient_id_obj})
        if not task_data:
            tasks = []
        else:
            tasks = task_data.get('tasks', [])
        
        # Get medication data
        med_data = db.medications.find_one({"user_id": patient_id_obj})
        if not med_data:
            medications = []
        else:
            medications = med_data.get('medications', [])
            
            # Sort medications by time
            def time_key(med):
                try:
                    return datetime.strptime(med['time'], '%I:%M %p').time()
                except:
                    return datetime.min.time()
                    
            medications = sorted(medications, key=time_key)
        
        # Get notes data
        notes_data = db.notes.find_one({"user_id": patient_id_obj})
        if not notes_data:
            notes_content = ""
        else:
            notes_content = notes_data.get('content', "")
        
        # Get all MMSE assessments for this patient
        mmse_assessments = list(db.mmse_results.find(
            {"user_id": patient_id_obj}
        ).sort("test_date", -1))
        
        # Get all severity assessments
        severity_assessments = list(db.severity_assessments.find(
            {"user_id": patient_id_obj}
        ).sort("assessment_date", -1))
        
        # Get latest severity assessment
        severity_data = severity_assessments[0] if severity_assessments else None
        
        # Calculate progress metrics
        progress_data = None
        if len(mmse_assessments) >= 2:
            latest = mmse_assessments[0]
            previous = mmse_assessments[1]
            improvement = latest.get('total_score', 0) - previous.get('total_score', 0)
            improvement_pct = (improvement / previous.get('total_score', 1)) * 100 if previous.get('total_score', 0) > 0 else 0
            progress_data = {
                'improvement': improvement,
                'improvement_pct': improvement_pct,
                'latest_score': latest.get('total_score', 0),
                'previous_score': previous.get('total_score', 0)
            }
        
        return render_template('manage_patient.html',
                              patient=patient,
                              tasks=tasks,
                              medications=medications,
                              notes_content=notes_content,
                              severity_data=severity_data,
                              mmse_assessments=mmse_assessments,
                              severity_assessments=severity_assessments,
                              progress_data=progress_data)
                              
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/update_patient_info/<patient_id>', methods=['POST'])
def update_patient_info(patient_id):
    if 'user_id' not in session or session.get('user_type') != 'caretaker':
        return redirect(url_for('login'))
    
    if not check_db_connection() or db is None:
        flash('Database connection error', 'danger')
        return redirect(url_for('dashboard'))
    
    try:
        patient_id_obj = ObjectId(patient_id)
        personal_info = request.form.get('personal_info', '')
        
        db.users.update_one(
            {"_id": patient_id_obj},
            {"$set": {"personal_info": personal_info}}
        )
        
        flash('Patient information updated successfully', 'success')
        return redirect(url_for('manage_patient', patient_id=patient_id))
        
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/add_patient_task/<patient_id>', methods=['POST'])
def add_patient_task(patient_id):
    if 'user_id' not in session or session.get('user_type') != 'caretaker':
        return redirect(url_for('login'))
    
    if not check_db_connection() or db is None:
        flash('Database connection error', 'danger')
        return redirect(url_for('dashboard'))
    
    try:
        patient_id_obj = ObjectId(patient_id)
        task_text = request.form.get('task_text')
        
        db.tasks.update_one(
            {"user_id": patient_id_obj},
            {"$push": {"tasks": {"text": task_text, "completed": False}}},
            upsert=True
        )
        
        flash('Task added successfully', 'success')
        return redirect(url_for('manage_patient', patient_id=patient_id))
        
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('manage_patient', patient_id=patient_id))

@app.route('/add_patient_medication/<patient_id>', methods=['POST'])
def add_patient_medication(patient_id):
    if 'user_id' not in session or session.get('user_type') != 'caretaker':
        return redirect(url_for('login'))
    
    if not check_db_connection() or db is None:
        flash('Database connection error', 'danger')
        return redirect(url_for('dashboard'))
    
    try:
        patient_id_obj = ObjectId(patient_id)
        med_name = request.form.get('med_name')
        med_time = request.form.get('med_time')
        
        if med_name and med_time:
            # Validate time format
            try:
                # Try to parse the time to validate format
                time_obj = datetime.strptime(med_time, '%I:%M %p')
                
                new_med = {
                    "id": str(datetime.now().timestamp()),
                    "name": med_name,
                    "time": med_time,
                }
                
                db.medications.update_one(
                    {"user_id": patient_id_obj},
                    {"$push": {"medications": new_med}},
                    upsert=True
                )
                
                flash('Medication added successfully', 'success')
            except ValueError:
                flash('Invalid time format. Please use HH:MM AM/PM', 'danger')
        
        return redirect(url_for('manage_patient', patient_id=patient_id))
        
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('manage_patient', patient_id=patient_id))

@app.route('/update_patient_notes/<patient_id>', methods=['POST'])
def update_patient_notes(patient_id):
    if 'user_id' not in session or session.get('user_type') != 'caretaker':
        return redirect(url_for('login'))
    
    if not check_db_connection() or db is None:
        flash('Database connection error', 'danger')
        return redirect(url_for('dashboard'))
    
    try:
        patient_id_obj = ObjectId(patient_id)
        content = request.form.get('content')
        
        db.notes.update_one(
            {"user_id": patient_id_obj},
            {"$set": {"content": content, "updated_at": datetime.now()}},
            upsert=True
        )
        
        flash('Notes updated successfully', 'success')
        return redirect(url_for('manage_patient', patient_id=patient_id))
        
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('manage_patient', patient_id=patient_id))

# Error handlers
@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', message="Internal server error. Please try again later."), 500

@app.route('/db_status')
def db_status():
    """Route to check database connection status - admin use only"""
    try:
        if db is None:
            return jsonify({"status": "error", "message": "MongoDB connection not established"})
        
        # Try to ping the database
        db.command('ping')
        return jsonify({
            "status": "connected", 
            "message": "MongoDB connection is working", 
            "collections": db.list_collection_names()
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

# Add session middleware to detect standalone mode
@app.before_request
def handle_standalone_mode():
    """Check and propagate standalone mode flag"""
    # Check if we have standalone in the session
    if session.get('standalone'):
        # Add it to g object for templates
        g.standalone = True
    
    # Also check query parameter
    if request.args.get('standalone') == 'true':
        session['standalone'] = True
        g.standalone = True

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7000, debug=True, use_reloader=False)

# Made with Bob
