#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
from datetime import datetime
import time
from difflib import SequenceMatcher

# Fix Unicode on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# تحديد المسارات الصحيحة
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

# مسارات Flask
TEMPLATE_FOLDER = os.path.join(PROJECT_ROOT, 'templates')
DATA_PATH = os.path.join(PROJECT_ROOT, 'data', 'quran.json')

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS

# إنشاء التطبيق مع المسارات الصحيحة
app = Flask(__name__, template_folder=TEMPLATE_FOLDER)
app.config['SECRET_KEY'] = 'quran-live-secret-2024'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

print("\n" + "="*70)
print("🌙 QURAN LIVE TRANSLATION")
print("="*70)
print(f"📁 Base: {BASE_DIR}")
print(f"📁 Root: {PROJECT_ROOT}")
print(f"📁 Templates: {TEMPLATE_FOLDER}")
print(f"📁 Data: {DATA_PATH}")
print(f"✓ Templates exists: {os.path.exists(TEMPLATE_FOLDER)}")
print(f"✓ Data exists: {os.path.exists(DATA_PATH)}")

# تحميل البيانات
quran_data = {}
try:
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        quran_data = json.load(f)
    print(f"✅ Loaded {len(quran_data)} surahs")
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)

# بناء الفهرس
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

print(f"✅ Indexed {len(verses_index)} verses")
print("="*70 + "\n")

current_surah = None
last_ayah = None

def normalize(text):
    import re
    if not text:
        return ""
    
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
    
    text_lower = text.lower()
    for variant, original in muqattaat_map.items():
        if text_lower.startswith(variant):
            text = original + text[len(variant):]
            break
    
    text = re.sub(r'[ًٌٍَُِّْـ]', '', text)
    text = re.sub(r'[^\w\s]', '', text)
    text = text.replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا')
    text = text.replace('ى', 'ي').replace('ة', 'ه')
    text = text.replace('ؤ', 'و').replace('ئ', 'ي')
    
    return text.strip().lower()

def similarity(text1, text2):
    if not text1 or not text2:
        return 0.0
    return SequenceMatcher(None, text1, text2).ratio()

def search_verse(text):
    global current_surah, last_ayah
    
    normalized = normalize(text)
    if len(normalized) < 2:
        return None
    
    if current_surah and last_ayah:
        for offset in range(1, 4):
            next_ayah = last_ayah + offset
            next_key = f"{current_surah}:{next_ayah}"
            if next_key in verses_index:
                expected = verses_index[next_key]
                score = similarity(normalized, normalize(expected['ar']))
                if score >= 0.50:
                    last_ayah = next_ayah
                    return expected
    
    best_match = None
    best_score = 0.0
    
    text_len = len(normalized)
    min_len = max(1, text_len - int(text_len * 0.4))
    max_len = text_len + int(text_len * 0.4)
    
    text_words = set(normalized.split())
    if len(text_words) >= 2:
        for key, verse in verses_index.items():
            verse_norm = normalize(verse['ar'])
            verse_words = set(verse_norm.split())
            
            common_words = text_words & verse_words
            if len(common_words) >= min(2, len(text_words) * 0.5):
                score = similarity(normalized, verse_norm)
                
                if score > best_score:
                    best_score = score
                    best_match = verse
                
                if score > 0.90:
                    current_surah = verse['surah']
                    last_ayah = verse['ayah']
                    return verse
    
    if best_score < 0.50:
        for key, verse in verses_index.items():
            verse_norm = normalize(verse['ar'])
            verse_len = len(verse_norm)
            
            if verse_len < min_len or verse_len > max_len:
                continue
            
            score = similarity(normalized, verse_norm)
            
            if score > best_score:
                best_score = score
                best_match = verse
    
    if best_score >= 0.45:
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
    lang = request.args.get('lang', 'en')
    return render_template('live.html', lang=lang)

@app.route('/mobile')
def mobile():
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
    print("✓ Client connected")
    emit('connection_status', {'connected': True})

@socketio.on('disconnect')
def handle_disconnect():
    print("✗ Client disconnected")

@socketio.on('set_surah')
def handle_set_surah(data):
    global current_surah, last_ayah
    surah = data.get('surah')
    if surah:
        current_surah = surah
        last_ayah = 0
        print(f"📖 Surah: {surah}")
        emit('surah_set', {'surah': surah}, broadcast=True)

@socketio.on('reset_matcher')
def handle_reset():
    global current_surah, last_ayah
    current_surah = None
    last_ayah = None
    print("🔄 Reset")
    emit('matcher_reset', {'message': 'Reset successful'}, broadcast=True)

@socketio.on('recognize_verse')
def handle_recognize(data):
    text = data.get('text', '').strip()
    lang = data.get('lang', 'en')
    
    if not text:
        return
    
    start_time = time.time()
    
    print(f"🔍 Search: {text[:50]}... | Lang: {lang}")
    verse = search_verse(text)
    
    response_time = (time.time() - start_time) * 1000
    
    if verse:
        print(f"✅ Found: {verse['surah']}:{verse['ayah']} ({response_time:.1f}ms)")
        
        confidence = similarity(normalize(text), normalize(verse['ar']))
        
        verse_data = {
            'surah': verse['surah'],
            'ayah': verse['ayah'],
            'ar': verse['ar'],
            'en': verse.get('en', ''),
            'fr': verse.get('fr', ''),
            'nl': verse.get('nl', ''),
            'translation': verse.get(lang, verse.get('en', ''))
        }
        
        print(f"📝 Translation ({lang}): {verse_data['translation'][:50]}...")
        
        emit('verse_matched', {
            'verse': verse_data,
            'confidence': round(confidence, 2),
            'response_time_ms': round(response_time, 1)
        }, broadcast=True)
        
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
        print(f"❌ Not found ({response_time:.1f}ms)")
        emit('no_match', {
            'reason': 'not_found',
            'response_time_ms': round(response_time, 1)
        })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    print("\n" + "="*70)
    print("🚀 Starting Server")
    print(f"📡 Port: {port}")
    print("="*70 + "\n")
    
    socketio.run(
        app,
        host='0.0.0.0',
        port=port,
        debug=False,
        allow_unsafe_werkzeug=True
    )
