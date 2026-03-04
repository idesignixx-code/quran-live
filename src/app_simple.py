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

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS

app = Flask(__name__)
app.config['SECRET_KEY'] = 'quran-live-secret-2024'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# تحديد مسار البيانات
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(os.path.dirname(BASE_DIR), 'data', 'quran.json')

print("\n" + "="*70)
print("🌙 QURAN LIVE TRANSLATION - Simple Mode")
print("="*70)
print(f"📁 Data path: {DATA_PATH}")
print(f"✓ File exists: {os.path.exists(DATA_PATH)}")

# تحميل البيانات
quran_data = {}
try:
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        quran_data = json.load(f)
    print(f"✅ Loaded {len(quran_data)} surahs successfully")
except Exception as e:
    print(f"❌ Error loading data: {e}")
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

# حالة التنبؤ التسلسلي
current_surah = None
last_ayah = None

# دالة التطبيع
def normalize(text):
    import re
    if not text:
        return ""
    
    # معالجة الحروف المقطعة
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
    
    # إزالة التشكيل
    text = re.sub(r'[ًٌٍَُِّْـ]', '', text)
    # إزالة الأحرف الخاصة
    text = re.sub(r'[^\w\s]', '', text)
    # توحيد الأحرف
    text = text.replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا')
    text = text.replace('ى', 'ي').replace('ة', 'ه')
    text = text.replace('ؤ', 'و').replace('ئ', 'ي')
    
    return text.strip().lower()

# دالة حساب التشابه
def similarity(text1, text2):
    if not text1 or not text2:
        return 0.0
    return SequenceMatcher(None, text1, text2).ratio()

# دالة البحث المحسّنة
def search_verse(text):
    global current_surah, last_ayah
    
    normalized = normalize(text)
    if len(normalized) < 2:
        return None
    
    # محاولة التنبؤ التسلسلي أولاً
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
    
    # حساب طول النص
    text_len = len(normalized)
    min_len = max(1, text_len - int(text_len * 0.4))
    max_len = text_len + int(text_len * 0.4)
    
    # بحث سريع بالكلمات
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
    
    # بحث كامل
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
    
    # إرجاع النتيجة
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
        print(f"📖 Surah set to: {surah}")
        emit('surah_set', {'surah': surah}, broadcast=True)

@socketio.on('reset_matcher')
def handle_reset():
    global current_surah, last_ayah
    current_surah = None
    last_ayah = None
    print("🔄 Matcher reset")
    emit('matcher_reset', {'message': 'Reset successful'}, broadcast=True)

@socketio.on('recognize_verse')
def handle_recognize(data):
    text = data.get('text', '').strip()
    lang = data.get('lang', 'en')
    
    if not text:
        return
    
    start_time = time.time()
    
    print(f"🔍 Searching: {text[:50]}... | Lang: {lang}")
    verse = search_verse(text)
    
    response_time = (time.time() - start_time) * 1000
    
    if verse:
        print(f"✅ Found: {verse['surah']}:{verse['ayah']} ({response_time:.1f}ms)")
        
        confidence = similarity(normalize(text), normalize(verse['ar']))
        
        # إعداد بيانات الآية مع كل الترجمات
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
        
        # إرسال الآية
        emit('verse_matched', {
            'verse': verse_data,
            'confidence': round(confidence, 2),
            'source': 'simple_search',
            'response_time_ms': round(response_time, 1)
        }, broadcast=True)
        
        # الآيات التالية
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
        print(f"❌ No match ({response_time:.1f}ms)")
        emit('no_match', {
            'reason': 'not_found',
            'response_time_ms': round(response_time, 1)
        })

# Main
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    print("\n" + "="*70)
    print("🚀 Starting Quran Live Translation Server")
    print(f"📡 Port: {port}")
    print(f"🌍 Environment: {'Production' if os.environ.get('PORT') else 'Development'}")
    print("="*70 + "\n")
    
    socketio.run(
        app,
        host='0.0.0.0',
        port=port,
        debug=False,
        allow_unsafe_werkzeug=True
    )
