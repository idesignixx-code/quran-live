# -*- coding: utf-8 -*-
"""
نظام الترجمة الفورية للقرآن الكريم - نسخة مبسطة سريعة
Quick Start Version - No Freeze
"""

import sys
import os

# Fix Unicode on Windows
if sys.platform == 'win32':
    os.system('chcp 65001 > nul')

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import json
import time
from datetime import datetime

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(os.path.dirname(BASE_DIR), 'templates')
DATA_PATH = os.path.join(os.path.dirname(BASE_DIR), 'data', 'quran.json')

# Flask App
app = Flask(__name__, template_folder=TEMPLATE_DIR)
app.config['SECRET_KEY'] = 'quran-live-2025'

# Socket.IO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

print("\n" + "="*70)
print("Loading Quran data...")

# Load Quran Data
quran_data = {}
try:
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        quran_data = json.load(f)
    print(f"Loaded {len(quran_data)} surahs successfully")
except Exception as e:
    print(f"Error loading data: {e}")
    print(f"Looking for: {DATA_PATH}")

# Build simple index
verses_index = {}
for surah_num, surah in quran_data.items():
    for ayah in surah.get('ayahs', []):
        key = f"{surah_num}:{ayah.get('number', 0)}"
        verses_index[key] = {
            'surah': int(surah_num),
            'ayah': ayah.get('number', 0),
            'ar': ayah.get('ar', ''),
            'en': ayah.get('en', ''),
            'fr': ayah.get('fr', ''),
            'nl': ayah.get('nl', ''),
            'surah_name': surah.get('name', '')
        }

print(f"Indexed {len(verses_index)} verses")
print("="*70)

# Sequential prediction state
current_surah = None
last_ayah = None

# Advanced text normalizer (same as original)
def normalize(text):
    import re
    if not text:
        return ""
    
    # Handle common Muqatta'at (الحروف المقطعة)
    muqattaat_map = {
        'الف لام ميم': 'الم',
        'ألف لام ميم': 'الم',
        'الف لام را': 'الر',
        'كاف ها يا عين صاد': 'كهيعص',
        'يا سين': 'يس',
        'طا ها': 'طه',
        'طا سين ميم': 'طسم',
        'حا ميم': 'حم',
    }
    
    # Replace Muqatta'at
    text_lower = text.lower()
    for variant, original in muqattaat_map.items():
        if text_lower.startswith(variant):
            text = original + text[len(variant):]
            break
    
    # Remove diacritics
    text = re.sub(r'[ًٌٍَُِّْـ]', '', text)
    # Remove special characters
    text = re.sub(r'[^\w\s]', '', text)
    # Normalize specific Arabic letters
    text = text.replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا')
    text = text.replace('ى', 'ي').replace('ة', 'ه')
    text = text.replace('ؤ', 'و').replace('ئ', 'ي')
    
    return text.strip().lower()

# Calculate similarity
def similarity(text1, text2):
    from difflib import SequenceMatcher
    if not text1 or not text2:
        return 0.0
    return SequenceMatcher(None, text1, text2).ratio()

# Advanced search (optimized for fast reading)
def search_verse(text):
    global current_surah, last_ayah
    
    normalized = normalize(text)
    if len(normalized) < 2:  # تقليل الحد الأدنى من 3 إلى 2
        return None
    
    # Try sequential prediction first (most common in continuous reading)
    if current_surah and last_ayah:
        # Try next 3 verses (for fast sequential reading)
        for offset in range(1, 4):
            next_ayah = last_ayah + offset
            next_key = f"{current_surah}:{next_ayah}"
            if next_key in verses_index:
                expected = verses_index[next_key]
                score = similarity(normalized, normalize(expected['ar']))
                if score >= 0.55:  # تقليل العتبة من 0.65 إلى 0.55 للقراءة السريعة
                    last_ayah = next_ayah
                    return expected
    
    best_match = None
    best_score = 0.0
    
    # Calculate text length for filtering (more lenient)
    text_len = len(normalized)
    min_len = max(1, text_len - int(text_len * 0.4))  # زيادة التسامح من 0.3 إلى 0.4
    max_len = text_len + int(text_len * 0.4)
    
    # Quick partial match first (for speed)
    text_words = set(normalized.split())
    if len(text_words) >= 2:
        for key, verse in verses_index.items():
            verse_norm = normalize(verse['ar'])
            verse_words = set(verse_norm.split())
            
            # Quick word overlap check
            common_words = text_words & verse_words
            if len(common_words) >= min(2, len(text_words) * 0.5):
                score = similarity(normalized, verse_norm)
                
                if score > best_score:
                    best_score = score
                    best_match = verse
                
                # Early exit for very high confidence
                if score > 0.92:  # تقليل من 0.95
                    current_surah = verse['surah']
                    last_ayah = verse['ayah']
                    return verse
    
    # Full search if no quick match
    if best_score < 0.55:
        for key, verse in verses_index.items():
            verse_norm = normalize(verse['ar'])
            verse_len = len(verse_norm)
            
            # Skip if length difference is too large
            if verse_len < min_len or verse_len > max_len:
                continue
            
            # Calculate similarity
            score = similarity(normalized, verse_norm)
            
            # Update best match
            if score > best_score:
                best_score = score
                best_match = verse
    
    # Return if score is good enough (lowered threshold)
    if best_score >= 0.50:  # تقليل من 0.65 إلى 0.50
        if best_match:
            current_surah = best_match['surah']
            last_ayah = best_match['ayah']
        return best_match
    
    return None

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/live')
def live():
    """صفحة العرض المباشر مع دعم اللغات"""
    lang = request.args.get('lang', 'en')
    return render_template('live.html', lang=lang)

@app.route('/mobile')
def mobile():
    """صفحة الموبايل مع الميكروفون"""
    lang = request.args.get('lang', 'en')
    return render_template('mobile.html', lang=lang)

@app.route('/api/health')
def health():
    return jsonify({
        'status': 'ok',
        'verses': len(verses_index),
        'time': datetime.now().isoformat()
    })

@app.route('/api/verse/<int:surah>/<int:ayah>')
def get_verse(surah, ayah):
    key = f"{surah}:{ayah}"
    verse = verses_index.get(key)
    
    if verse:
        return jsonify({'verse': verse})
    return jsonify({'error': 'Not found'}), 404

# WebSocket Events
@socketio.on('connect')
def handle_connect():
    print("Client connected")
    emit('connection_status', {'connected': True})

@socketio.on('disconnect')
def handle_disconnect():
    print("Client disconnected")

@socketio.on('set_surah')
def handle_set_surah(data):
    global current_surah, last_ayah
    surah = data.get('surah')
    if surah:
        current_surah = surah
        last_ayah = 0
        print(f"Surah set to: {surah}")
        emit('surah_set', {'surah': surah}, broadcast=True)

@socketio.on('reset_matcher')
def handle_reset():
    global current_surah, last_ayah
    current_surah = None
    last_ayah = None
    print("Matcher reset")
    emit('matcher_reset', {'message': 'Reset successful'}, broadcast=True)

@socketio.on('audio_data')
def handle_audio(data):
    """
    معالجة الصوت من الموبايل
    """
    try:
        import base64
        import tempfile
        
        audio_base64 = data.get('audio', '')
        lang = data.get('lang', 'en')
        
        print(f"[AUDIO] Received audio data ({len(audio_base64)} bytes)")
        
        # Decode base64 audio
        audio_bytes = base64.b64decode(audio_base64)
        
        # Save temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_audio:
            temp_audio.write(audio_bytes)
            temp_path = temp_audio.name
        
        try:
            # Option 1: Using Web Speech API (recommended for mobile)
            # The transcription is done in the browser, so we receive text directly
            
            # Option 2: Using Whisper (requires: pip install openai-whisper)
            # Uncomment this when you install Whisper:
            """
            import whisper
            model = whisper.load_model("base")
            result = model.transcribe(temp_path, language="ar")
            text = result["text"]
            print(f"[AUDIO] Transcribed: {text}")
            
            # Send to recognition
            emit('recognize_verse', {
                'text': text,
                'lang': lang
            }, broadcast=True)
            """
            
            # For now, send notification that audio was received
            print("[AUDIO] Audio received successfully")
            emit('audio_received', {
                'status': 'success',
                'message': 'Audio received. Install Whisper for transcription.'
            })
            
        finally:
            # Clean up temp file
            import os
            if os.path.exists(temp_path):
                os.remove(temp_path)
        
    except Exception as e:
        print(f"[AUDIO] Error processing audio: {e}")
        emit('error', {'message': 'Failed to process audio'})

@socketio.on('recognize_verse')
def handle_recognize(data):
    text = data.get('text', '').strip()
    lang = data.get('lang', 'en')
    
    if not text:
        return
    
    start_time = time.time()
    
    print(f"Searching: {text[:50]}... (lang={lang})")
    verse = search_verse(text)
    
    response_time = (time.time() - start_time) * 1000
    
    if verse:
        print(f"Found: {verse['surah']}:{verse['ayah']} ({response_time:.1f}ms)")
        
        # Calculate confidence
        confidence = similarity(normalize(text), normalize(verse['ar']))
        
        # Get translation for the requested language
        translation = verse.get(lang, verse.get('en', ''))
        
        # Debug log
        print(f"Translation ({lang}): {translation[:50]}...")
        
        # Send matched verse with all language data
        emit('verse_matched', {
            'verse': {
                'surah': verse['surah'],
                'ayah': verse['ayah'],
                'ar': verse['ar'],
                'en': verse.get('en', ''),
                'fr': verse.get('fr', ''),
                'nl': verse.get('nl', ''),
                'translation': translation  # For backward compatibility
            },
            'confidence': round(confidence, 2),
            'source': 'simple_search',
            'response_time_ms': round(response_time, 1)
        }, broadcast=True)
        
        # Get next verses (3 verses)
        next_verses = []
        for i in range(1, 4):
            next_ayah = verse['ayah'] + i
            next_key = f"{verse['surah']}:{next_ayah}"
            if next_key in verses_index:
                nv = verses_index[next_key]
                next_verses.append({
                    'surah': nv['surah'],
                    'ayah': nv['ayah'],
                    'ar': nv['ar'],
                    'en': nv.get('en', ''),
                    'fr': nv.get('fr', ''),
                    'nl': nv.get('nl', ''),
                    'translation': nv.get(lang, nv.get('en', ''))
                })
        
        if next_verses:
            emit('next_verses', {
                'verses': next_verses,
                'count': len(next_verses)
            }, broadcast=True)
    else:
        print(f"No match found ({response_time:.1f}ms)")
        emit('no_match', {
            'reason': 'not_found',
            'response_time_ms': round(response_time, 1)
        })

# Main
if __name__ == '__main__':
    print("\n" + "="*70)
    print("Starting server...")
    print("Open: http://localhost:5000")
    print("="*70 + "\n")
    
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=False
    )
